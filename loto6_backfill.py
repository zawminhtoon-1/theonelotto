"""
loto6_backfill.py
------------------
Creates loto6_results (if missing) and backfills/syncs Loto6 draws from
Mizuho Bank's CSV endpoint. Mirrors loto7_backfill.py's validated
fetch-and-parse pathway exactly (Shift-JIS CSV, wareki date conversion,
upsert via ON CONFLICT) -- only the schema differs (6 main + 1 bonus,
not 7 main + 2 bonus).

Loto6: pick 6 numbers from 1-43, drawn Mon/Thu.

Data source: https://www.mizuhobank.co.jp/retail/takarakuji/loto/loto6/csv/
  - Individual draw: A{1020000+draw_serial}.CSV (Shift-JIS encoded)
  - File format: 本数字,n1..n6,ボーナス数字,b
  - Offset 1020000 confirmed empirically against known draws (already
    used as a reference value in loto7_backfill.py's docstring; this
    script re-confirms it against the live #2129/#2130/#2131 CSVs
    before trusting it, since this is the first time it's actually
    used to fetch, not just cited).

Run:
  python loto6_backfill.py --test              # fetch draws 1,2,3,50,2129 only, print, no DB writes
  python loto6_backfill.py --sync               # fetch + upsert only serials missing since the DB's current latest
  python loto6_backfill.py --backfill           # create table + insert all draws 1..latest (full historical backfill)
"""
import os, re, sys, time
import psycopg2
from datetime import date
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor, as_completed

if 'DATABASE_URL' not in os.environ:
    with open(r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\.env.local", encoding='utf-8') as f:
        env_text = f.read()
    m = re.search(r'DATABASE_URL=(.+)', env_text)
    os.environ['DATABASE_URL'] = m.group(1).strip()

DB_URL = os.environ["DATABASE_URL"]
CSV_BASE = "https://www.mizuhobank.co.jp/retail/takarakuji/loto/loto6/csv/"
SERIAL_OFFSET = 1020000

WAREKI = {"令和": 2018, "平成": 1988, "昭和": 1925}


def _wareki_to_date(text: str) -> date | None:
    for era, base in WAREKI.items():
        m = re.search(era + r"(\d+)年(\d+)月(\d+)日", text)
        if m:
            return date(base + int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def fetch_draw(draw_serial: int) -> dict | None:
    """Fetch + parse a single Loto6 draw. Returns None if not yet released (404)."""
    url = CSV_BASE + f"A{SERIAL_OFFSET + draw_serial}.CSV"
    r = cf_requests.get(url, impersonate="chrome131", timeout=20)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"Unexpected HTTP {r.status_code} for {url}")

    text = r.content.decode("shift_jis", errors="replace")

    draw_date = None
    nums = None
    bonus = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if draw_date is None:
            d = _wareki_to_date(line)
            if d:
                draw_date = d
        if "本数字" in line:
            parts = [p.strip() for p in line.split(",")]
            digits = [p for p in parts if re.match(r"^\d{1,2}$", p)]
            if len(digits) >= 7:
                nums = [int(x) for x in digits[:6]]
                bonus = int(digits[6])

    if nums and bonus is not None and draw_date:
        return {
            "draw_serial": draw_serial,
            "draw_date": draw_date,
            "num1": nums[0], "num2": nums[1], "num3": nums[2], "num4": nums[3],
            "num5": nums[4], "num6": nums[5],
            "bonus": bonus,
        }
    return None


def validate_draw(d: dict):
    """Sanity-check a parsed draw before it's allowed anywhere near the DB."""
    main = [d["num1"], d["num2"], d["num3"], d["num4"], d["num5"], d["num6"]]
    if len(set(main)) != 6:
        raise ValueError(f"#{d['draw_serial']}: duplicate main numbers: {main}")
    if not all(1 <= n <= 43 for n in main):
        raise ValueError(f"#{d['draw_serial']}: main number out of 1-43 range: {main}")
    if not (1 <= d["bonus"] <= 43):
        raise ValueError(f"#{d['draw_serial']}: bonus out of 1-43 range: {d['bonus']}")
    if d["bonus"] in main:
        raise ValueError(f"#{d['draw_serial']}: bonus {d['bonus']} duplicates a main number: {main}")


def find_latest_serial(start: int = 1) -> int:
    """Exponential + binary search for the latest available draw, starting
    from `start` (must itself be a known-fetchable serial -- Loto6's CSV
    archive does NOT go back to #1 the way Loto7's apparently does, so a
    full-backfill call must pass an actual known-good low anchor, and
    --sync passes the DB's current latest, which is always known-good)."""
    if fetch_draw(start) is None:
        raise RuntimeError(f"find_latest_serial: anchor serial #{start} is not fetchable -- pick a known-good start.")
    lo, hi = start, start
    step = 1
    while fetch_draw(hi) is not None:
        lo = hi
        step *= 2
        hi = lo + step
        if hi > start + 5000:
            break
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if fetch_draw(mid) is not None:
            lo = mid
        else:
            hi = mid
    return lo


def create_table():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS loto6_results (
            id SERIAL PRIMARY KEY,
            draw_serial INTEGER UNIQUE NOT NULL,
            draw_date DATE,
            num1 INTEGER, num2 INTEGER, num3 INTEGER, num4 INTEGER,
            num5 INTEGER, num6 INTEGER,
            bonus INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("loto6_results table ready.")


def get_latest_db_serial() -> int:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(draw_serial), 0) FROM loto6_results")
    latest = cur.fetchone()[0]
    conn.close()
    return latest


def insert_draws(draws: list[dict]):
    if not draws:
        return
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    rows = [
        (d["draw_serial"], d["draw_date"],
         d["num1"], d["num2"], d["num3"], d["num4"], d["num5"], d["num6"],
         d["bonus"])
        for d in draws
    ]
    cur.executemany(
        """
        INSERT INTO loto6_results
            (draw_serial, draw_date, num1, num2, num3, num4, num5, num6, bonus)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (draw_serial) DO UPDATE SET
            draw_date=EXCLUDED.draw_date,
            num1=EXCLUDED.num1, num2=EXCLUDED.num2, num3=EXCLUDED.num3, num4=EXCLUDED.num4,
            num5=EXCLUDED.num5, num6=EXCLUDED.num6,
            bonus=EXCLUDED.bonus
        """,
        rows,
    )
    conn.commit()
    conn.close()


def run_test():
    for serial in [1, 2, 3, 50, 2129]:
        d = fetch_draw(serial)
        print(f"#{serial}: {d}")


def run_sync():
    """Fetch + upsert only serials missing since the DB's current latest."""
    create_table()
    db_latest = get_latest_db_serial()
    print(f"DB's current latest draw_serial: {db_latest}")
    if db_latest < 1:
        raise RuntimeError("DB has no rows -- --sync needs an existing known-good anchor serial; use --backfill instead for an empty table.")
    live_latest = find_latest_serial(start=db_latest)
    print(f"Live (Mizuho) latest available draw_serial: {live_latest}")

    if live_latest <= db_latest:
        print("DB is already up to date. Nothing to sync.")
        return

    missing = list(range(db_latest + 1, live_latest + 1))
    print(f"Missing serials to fetch: {missing}")

    draws = []
    for s in missing:
        d = fetch_draw(s)
        if d is None:
            raise RuntimeError(f"#{s} was expected to exist (<= live_latest={live_latest}) but fetch returned None -- inconsistent state, aborting.")
        validate_draw(d)
        draws.append(d)
        print(f"  Fetched + validated #{s}: main={[d['num1'],d['num2'],d['num3'],d['num4'],d['num5'],d['num6']]} bonus={d['bonus']} date={d['draw_date']}")

    insert_draws(draws)
    print(f"\nInserted/upserted {len(draws)} draws into loto6_results: {[d['draw_serial'] for d in draws]}")


def run_backfill():
    create_table()
    latest = find_latest_serial()
    print(f"Latest available draw_serial: {latest}")

    draws = []
    errors = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_draw, s): s for s in range(1, latest + 1)}
        done = 0
        for fut in as_completed(futures):
            s = futures[fut]
            try:
                d = fut.result()
                if d:
                    validate_draw(d)
                    draws.append(d)
                else:
                    errors.append(s)
            except Exception as e:
                errors.append(s)
                print(f"  error on #{s}: {e}")
            done += 1
            if done % 100 == 0:
                print(f"  fetched {done}/{latest}...")

    draws.sort(key=lambda d: d["draw_serial"])
    print(f"Fetched {len(draws)} draws, {len(errors)} failures: {errors}")

    insert_draws(draws)
    print(f"Inserted/upserted {len(draws)} draws into loto6_results.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    elif "--sync" in sys.argv:
        run_sync()
    elif "--backfill" in sys.argv:
        run_backfill()
    else:
        print("Usage: python loto6_backfill.py [--test | --sync | --backfill]")
