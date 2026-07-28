"""
create_local_db.py
------------------
Creates a local SQLite DB with:
  1. loto6_combos  — all C(43,6) = 6,096,454 sorted combinations (master data)
  2. predict_transactions — per draw: predicted combos + actual result, with OK/NG flag

OK  = this is the actual winning combination for that draw
NG  = this combo was predicted but did not exactly match (use 'hits' for partial matches)

Usage:
  python create_local_db.py            # create schema + generate all 6M combos
  python create_local_db.py --import   # also import backtest.html predictions
"""
import sys, sqlite3, itertools, time, json, re

DB_PATH   = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\loto6_local.db"
HTML_PATH = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\backtest.html"

IMPORT_MODE = '--import' in sys.argv

# ── 1. Create / open DB ────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")

cur.executescript("""
CREATE TABLE IF NOT EXISTS loto6_combos (
    id  INTEGER PRIMARY KEY,
    n1  INTEGER NOT NULL,
    n2  INTEGER NOT NULL,
    n3  INTEGER NOT NULL,
    n4  INTEGER NOT NULL,
    n5  INTEGER NOT NULL,
    n6  INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_combo ON loto6_combos(n1,n2,n3,n4,n5,n6);

CREATE TABLE IF NOT EXISTS predict_transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    draw_serial  INTEGER NOT NULL,
    combo_id     INTEGER NOT NULL REFERENCES loto6_combos(id),
    method_name  TEXT,
    hits         INTEGER DEFAULT 0,  -- how many of the 6 actual numbers are in this combo
    bonus_hit    INTEGER DEFAULT 0,  -- 1 if bonus number is in this combo
    flag         TEXT NOT NULL,      -- 'OK' = actual winning combo, 'NG' = predicted but not exact match
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tx_serial ON predict_transactions(draw_serial);
CREATE INDEX IF NOT EXISTS idx_tx_combo  ON predict_transactions(combo_id);
CREATE INDEX IF NOT EXISTS idx_tx_flag   ON predict_transactions(flag);
CREATE INDEX IF NOT EXISTS idx_tx_hits   ON predict_transactions(hits);
""")
conn.commit()
print("Schema ready.")

# ── 2. Populate master combos (if not already done) ───────────────────────────
cur.execute("SELECT COUNT(*) FROM loto6_combos")
existing = cur.fetchone()[0]

if existing >= 6_096_454:
    print(f"Master combos already populated ({existing:,} rows). Skipping.")
else:
    print(f"Generating all C(43,6) = 6,096,454 combinations...")
    if existing > 0:
        print(f"  (resuming from {existing:,})")
    t0 = time.time()
    BATCH = 100_000
    batch = []
    row_id = existing + 1
    count  = 0
    # Fast combo lookup to find where we left off
    # For simplicity, regenerate from scratch with INSERT OR IGNORE
    row_id = 1
    for combo in itertools.combinations(range(1, 44), 6):
        batch.append((row_id,) + combo)
        row_id += 1
        count  += 1
        if len(batch) >= BATCH:
            cur.executemany(
                "INSERT OR IGNORE INTO loto6_combos(id,n1,n2,n3,n4,n5,n6) VALUES(?,?,?,?,?,?,?)",
                batch
            )
            conn.commit()
            batch = []
            elapsed = time.time() - t0
            pct = count / 6_096_454 * 100
            print(f"  {count:>7,} / 6,096,454  {pct:.1f}%  ({elapsed:.1f}s)")
    if batch:
        cur.executemany(
            "INSERT OR IGNORE INTO loto6_combos(id,n1,n2,n3,n4,n5,n6) VALUES(?,?,?,?,?,?,?)",
            batch
        )
        conn.commit()
    print(f"Done: {count:,} combos in {time.time()-t0:.1f}s")

# ── Combo lookup helper ────────────────────────────────────────────────────────
_combo_cache = {}
def get_combo_id(nums):
    """Look up ID for a sorted 6-tuple of numbers."""
    key = tuple(sorted(nums))
    if key in _combo_cache:
        return _combo_cache[key]
    cur.execute(
        "SELECT id FROM loto6_combos WHERE n1=? AND n2=? AND n3=? AND n4=? AND n5=? AND n6=?",
        key
    )
    row = cur.fetchone()
    if row:
        _combo_cache[key] = row[0]
        return row[0]
    return None

# ── 3. Optional: import backtest.html predictions ─────────────────────────────
if not IMPORT_MODE:
    print("\nRun with --import to also load backtest.html predictions into predict_transactions.")
    print(f"\nDB saved to {DB_PATH}")
    conn.close()
    sys.exit(0)

print("\nImporting backtest.html predictions...")
with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

m = re.search(r'const DATA\s*=\s*(\[)', html)
bs = m.start(1)
depth = 0; pos = bs
while pos < len(html):
    if html[pos] == '[': depth += 1
    elif html[pos] == ']':
        depth -= 1
        if depth == 0: be = pos + 1; break
    pos += 1
DATA = json.loads(html[bs:be])

m2 = re.search(r'const METHODS\s*=\s*(\[.*?\])', html, re.DOTALL)
METHODS = json.loads(m2.group(1))

print(f"Loaded {len(DATA)} draws, {len(METHODS)} methods")

cur.execute("SELECT COUNT(*) FROM predict_transactions")
existing_tx = cur.fetchone()[0]
if existing_tx > 0:
    print(f"predict_transactions already has {existing_tx:,} rows. Skipping import.")
    print(f"Delete existing rows first if you want to re-import.")
    conn.close()
    sys.exit(0)

t0 = time.time()
tx_batch = []
BATCH = 5000

for i, row in enumerate(DATA):
    serial = row['s']
    actual6 = sorted(row['a'])
    bonus   = row['b']
    actual_set = set(actual6)

    # Insert actual winning combo as OK
    actual_id = get_combo_id(actual6)
    if actual_id:
        tx_batch.append((serial, actual_id, 'actual', 6, 1 if bonus in actual6 else 0, 'OK'))

    # Insert each method's first 6-combo prediction as NG (or OK if exact match)
    for mi, pred in enumerate(row['p']):
        picks = pred[0]  # list of predicted numbers
        method = METHODS[mi] if mi < len(METHODS) else f'M{mi}'
        # Take first 6 from picks as the "main" combo for this method
        combo6 = sorted(picks[:6])
        hits   = len(set(combo6) & actual_set)
        bh     = int(bonus in combo6)
        flag   = 'OK' if hits == 6 else 'NG'
        cid    = get_combo_id(combo6)
        if cid:
            tx_batch.append((serial, cid, method, hits, bh, flag))

        if len(tx_batch) >= BATCH:
            cur.executemany(
                "INSERT INTO predict_transactions(draw_serial,combo_id,method_name,hits,bonus_hit,flag) VALUES(?,?,?,?,?,?)",
                tx_batch
            )
            conn.commit()
            tx_batch = []

    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(DATA)} draws  ({time.time()-t0:.1f}s)")

if tx_batch:
    cur.executemany(
        "INSERT INTO predict_transactions(draw_serial,combo_id,method_name,hits,bonus_hit,flag) VALUES(?,?,?,?,?,?)",
        tx_batch
    )
    conn.commit()

cur.execute("SELECT COUNT(*) FROM predict_transactions")
total_tx = cur.fetchone()[0]
print(f"\nImported {total_tx:,} rows into predict_transactions in {time.time()-t0:.1f}s")
print(f"DB saved to {DB_PATH}")
conn.close()
