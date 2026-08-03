"""
miniloto_backfill.py
----------------------
Creates miniloto_results (if missing) and backfills historical MiniLoto
draws from Mizuho Bank's CSV endpoint.

MiniLoto: pick 5 numbers from 1-31, plus 1 bonus number, drawn weekly on
Tuesdays. CSV format: 本数字,n1..n5,ボーナス数字,b1 (5 main + 1 bonus,
confirmed against live data -- NOT 2 bonus numbers like Loto7).

Data source: https://www.mizuhobank.co.jp/retail/takarakuji/loto/miniloto/csv/
  - Individual draw: A{1010000+draw_serial}.CSV (Shift-JIS encoded)
  - Offset 1010000 confirmed empirically (Loto6=1020000, Loto7=1030000).
  - Unlike Loto6/Loto7, the CSV archive does NOT go back to draw #1 --
    earliest available is #521 (2009-08-04); confirmed via binary search.
    Weekly Tuesday cadence confirmed (Aug 4 2009 was a Tuesday, and all
    sampled draws are exactly 7 days apart).
  - Spot-checked draw #1397 (2026-07-28) against independent sources --
    exact match on numbers (03,06,14,20,31 / bonus 17) AND prize amounts.

Run:
  python miniloto_backfill.py --test        # fetch a handful of draws only, print, no DB writes
  python miniloto_backfill.py --backfill    # create table + insert all available draws
"""
import os, re, sys, time
import psycopg2
from datetime import date
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_URL = os.environ["DATABASE_URL"]
CSV_BASE = "https://www.mizuhobank.co.jp/retail/takarakuji/loto/miniloto/csv/"
SERIAL_OFFSET = 1010000

WAREKI = {"令和": 2018, "平成": 1988, "昭和": 1925}


def _wareki_to_date(text: str) -> date | None:
    for era, base in WAREKI.items():
        m = re.search(era + r"(\d+)年(\d+)月(\d+)日", text)
        if m:
            return date(base + int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def fetch_draw(draw_serial: int) -> dict | None:
    """Fetch + parse a single MiniLoto draw. Returns None if not available (404)."""
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
            if len(digits) >= 6:
                nums = [int(x) for x in digits[:5]]
                bonus = int(digits[5])

    if nums and bonus is not None and draw_date:
        return {
            "draw_serial": draw_serial,
            "draw_date": draw_date,
            "num1": nums[0], "num2": nums[1], "num3": nums[2],
            "num4": nums[3], "num5": nums[4],
            "bonus": bonus,
        }
    return None


def find_bounds() -> tuple[int, int]:
    """Binary/exponential search for earliest and latest available draw serials."""
    # Earliest: search between 1 (assume unavailable) and a known-good anchor.
    anchor = 1000
    while fetch_draw(anchor) is None:
        anchor += 200
        if anchor > 5000:
            raise RuntimeError("Could not find any available MiniLoto draw to anchor search")
    lo, hi = 1, anchor
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fetch_draw(mid) is not None:
            hi = mid
        else:
            lo = mid
    earliest = hi

    # Latest: exponential search upward from anchor.
    lo2, hi2 = anchor, anchor
    while fetch_draw(hi2) is not None:
        lo2 = hi2
        hi2 += 200
        if hi2 > 5000:
            break
    while lo2 < hi2 - 1:
        mid = (lo2 + hi2) // 2
        if fetch_draw(mid) is not None:
            lo2 = mid
        else:
            hi2 = mid
    latest = lo2

    return earliest, latest


def create_table():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS miniloto_results (
            id SERIAL PRIMARY KEY,
            draw_serial INTEGER UNIQUE NOT NULL,
            draw_date DATE,
            num1 INTEGER, num2 INTEGER, num3 INTEGER, num4 INTEGER, num5 INTEGER,
            bonus INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("miniloto_results table ready.")


def insert_draws(draws: list[dict]):
    if not draws:
        return
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    rows = [
        (d["draw_serial"], d["draw_date"],
         d["num1"], d["num2"], d["num3"], d["num4"], d["num5"], d["bonus"])
        for d in draws
    ]
    cur.executemany(
        """
        INSERT INTO miniloto_results
            (draw_serial, draw_date, num1, num2, num3, num4, num5, bonus)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (draw_serial) DO UPDATE SET
            draw_date=EXCLUDED.draw_date,
            num1=EXCLUDED.num1, num2=EXCLUDED.num2, num3=EXCLUDED.num3,
            num4=EXCLUDED.num4, num5=EXCLUDED.num5, bonus=EXCLUDED.bonus
        """,
        rows,
    )
    conn.commit()
    conn.close()


def run_test():
    for serial in [521, 522, 523, 600, 700, 1000, 1397]:
        d = fetch_draw(serial)
        print(f"#{serial}: {d}")


def run_backfill():
    create_table()
    earliest, latest = find_bounds()
    print(f"Available draw range: #{earliest} to #{latest}")

    draws = []
    errors = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_draw, s): s for s in range(earliest, latest + 1)}
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
                print(f"  fetched {done}/{latest-earliest+1}...")

    draws.sort(key=lambda d: d["draw_serial"])
    print(f"Fetched {len(draws)} draws, {len(errors)} failures: {errors}")

    insert_draws(draws)
    print(f"Inserted/upserted {len(draws)} draws into miniloto_results.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    elif "--backfill" in sys.argv:
        run_backfill()
    else:
        print("Usage: python miniloto_backfill.py [--test | --backfill]")
