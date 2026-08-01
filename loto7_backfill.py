"""
loto7_backfill.py
------------------
Creates loto7_results (if missing) and backfills historical Loto7 draws
from Mizuho Bank's CSV endpoint.

Loto7: pick 7 numbers from 1-37, drawn weekly on Fridays. CSV format has
7 main numbers + 2 bonus numbers (unlike Loto6's 6 main + 1 bonus).

Data source: https://www.mizuhobank.co.jp/retail/takarakuji/loto/loto7/csv/
  - Individual draw: A{1030000+draw_serial}.CSV (Shift-JIS encoded)
  - File format: 本数字,n1..n7,ボーナス数字,b1,b2
  - Offset 1030000 confirmed empirically (Loto6 uses 1020000); draw #1 is
    2013-04-05, confirmed weekly Friday cadence through draw #688 (2026-07-31).

Run:
  python loto7_backfill.py --test        # fetch draws 1,2,3,50,688 only, print, no DB writes
  python loto7_backfill.py --backfill    # create table + insert all draws 1..latest
"""
import os, re, sys, time
import psycopg2
from datetime import date
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def find_latest_serial() -> int:
    """Exponential + binary search for the latest available draw."""
    lo, hi = 1, 1
    while fetch_draw(hi) is not None:
        lo = hi
        hi *= 2
        if hi > 5000:
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
    elif "--backfill" in sys.argv:
        run_backfill()
    else:
        print("Usage: python loto7_backfill.py [--test | --backfill]")
