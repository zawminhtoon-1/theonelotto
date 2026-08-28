"""
loto7_backfill.py
------------------
Creates loto7_results (if missing) and backfills/syncs Loto7 draws from
Mizuho Bank's CSV endpoint. Mirrors loto6_backfill.py's --sync mode
(added there first) -- fetch-and-parse pathway, validate_draw() sanity
check, and upsert via ON CONFLICT are identical; only the schema differs
(7 main + 2 bonus, not 6 main + 1 bonus).

Loto7: pick 7 numbers from 1-37, drawn weekly on Fridays. CSV format has
7 main numbers + 2 bonus numbers (unlike Loto6's 6 main + 1 bonus).

Data source: https://www.mizuhobank.co.jp/retail/takarakuji/loto/loto7/csv/
  - Individual draw: A{1030000+draw_serial}.CSV (Shift-JIS encoded)
  - File format: 本数字,n1..n7,ボーナス数字,b1,b2
  - Offset 1030000 confirmed empirically (Loto6 uses 1020000); draw #1 is
    2013-04-05, confirmed weekly Friday cadence through draw #688 (2026-07-31).

Run:
  python loto7_backfill.py --test        # fetch draws 1,2,3,50,688 only, print, no DB writes
  python loto7_backfill.py --sync        # fetch + upsert only serials missing since the DB's current latest
  python loto7_backfill.py --backfill    # create table + insert all draws 1..latest
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
CSV_BASE = "https://www.mizuhobank.co.jp/retail/takarakuji/loto/loto7/csv/"
SERIAL_OFFSET = 1030000

WAREKI = {"令和": 2018, "平成": 1988, "昭和": 1925}


def _wareki_to_date(text: str) -> date | None:
    for era, base in WAREKI.items():
        m = re.search(era + r"(\d+)年(\d+)月(\d+)日", text)
        if m:
            return date(base + int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def fetch_draw(draw_serial: int) -> dict | None:
    """Fetch + parse a single Loto7 draw. Returns None if not yet released (404)."""
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
            if len(digits) >= 9:
                nums = [int(x) for x in digits[:7]]
                bonus = [int(x) for x in digits[7:9]]

    if nums and bonus and draw_date:
        return {
            "draw_serial": draw_serial,
            "draw_date": draw_date,
            "num1": nums[0], "num2": nums[1], "num3": nums[2], "num4": nums[3],
            "num5": nums[4], "num6": nums[5], "num7": nums[6],
            "bonus1": bonus[0], "bonus2": bonus[1],
        }
    return None


def validate_draw(d: dict):
    """Sanity-check a parsed draw before it's allowed anywhere near the DB."""
    main = [d["num1"], d["num2"], d["num3"], d["num4"], d["num5"], d["num6"], d["num7"]]
    if len(set(main)) != 7:
        raise ValueError(f"#{d['draw_serial']}: duplicate main numbers: {main}")
    if not all(1 <= n <= 37 for n in main):
        raise ValueError(f"#{d['draw_serial']}: main number out of 1-37 range: {main}")
    bonus = [d["bonus1"], d["bonus2"]]
    if len(set(bonus)) != 2:
        raise ValueError(f"#{d['draw_serial']}: duplicate bonus numbers: {bonus}")
    if not all(1 <= b <= 37 for b in bonus):
        raise ValueError(f"#{d['draw_serial']}: bonus out of 1-37 range: {bonus}")
    if set(bonus) & set(main):
        raise ValueError(f"#{d['draw_serial']}: bonus {bonus} duplicates a main number: {main}")


def find_latest_serial(start: int = 1) -> int:
    """Exponential + binary search for the latest available draw, starting
    from `start` (must itself be a known-fetchable serial -- --sync passes
    the DB's current latest, which is always known-good)."""
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
        CREATE TABLE IF NOT EXISTS loto7_results (
            id SERIAL PRIMARY KEY,
            draw_serial INTEGER UNIQUE NOT NULL,
            draw_date DATE,
            num1 INTEGER, num2 INTEGER, num3 INTEGER, num4 INTEGER,
            num5 INTEGER, num6 INTEGER, num7 INTEGER,
            bonus1 INTEGER, bonus2 INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("loto7_results table ready.")


def get_latest_db_serial() -> int:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(draw_serial), 0) FROM loto7_results")
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
         d["num1"], d["num2"], d["num3"], d["num4"], d["num5"], d["num6"], d["num7"],
         d["bonus1"], d["bonus2"])
        for d in draws
    ]
    cur.executemany(
        """
        INSERT INTO loto7_results
            (draw_serial, draw_date, num1, num2, num3, num4, num5, num6, num7, bonus1, bonus2)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (draw_serial) DO UPDATE SET
            draw_date=EXCLUDED.draw_date,
            num1=EXCLUDED.num1, num2=EXCLUDED.num2, num3=EXCLUDED.num3, num4=EXCLUDED.num4,
            num5=EXCLUDED.num5, num6=EXCLUDED.num6, num7=EXCLUDED.num7,
            bonus1=EXCLUDED.bonus1, bonus2=EXCLUDED.bonus2
        """,
        rows,
    )
    conn.commit()
    conn.close()


def run_test():
    for serial in [1, 2, 3, 50, 100, 688]:
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
        print(f"  Fetched + validated #{s}: main={[d['num1'],d['num2'],d['num3'],d['num4'],d['num5'],d['num6'],d['num7']]} "
              f"bonus={[d['bonus1'],d['bonus2']]} date={d['draw_date']}")

    insert_draws(draws)
    print(f"\nInserted/upserted {len(draws)} draws into loto7_results: {[d['draw_serial'] for d in draws]}")


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
    print(f"Inserted/upserted {len(draws)} draws into loto7_results.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    elif "--sync" in sys.argv:
        run_sync()
    elif "--backfill" in sys.argv:
        run_backfill()
    else:
        print("Usage: python loto7_backfill.py [--test | --sync | --backfill]")
