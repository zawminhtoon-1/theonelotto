"""
LSTM training + walk-forward backtest for Loto 6
Architecture: SEQ=10, H=16, IN=43, OUT=43 (multi-label binary)
N_PICKS=28, backtest last 1000 draws, match against 7 numbers (6 main + bonus)
Outputs: lstm_weights.json, lstm_backtest.json
"""
import numpy as np, json, time, psycopg2

DB_URL = (
    "postgresql://neondb_owner:npg_QbHpRZW8of3C"
    "@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require"
)

SEQ    = 10
H      = 16
IN     = 43
OUT    = 43
N_PICKS = 7
BT_DRAWS = 1000

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20.0, 20.0)))

class LSTM:
    def __init__(self, seed=42):
        np.random.seed(seed)
        self.H, self.I = H, IN
        n_xh = IN + H
        sc = np.sqrt(2.0 / (IN + H))
        self.W  = np.random.randn(4*H, n_xh) * sc
        self.b  = np.zeros(4*H)
        self.b[H:2*H] = 1.0
        self.Wy = np.random.randn(OUT, H) * np.sqrt(2.0 / (H + OUT))
        self.by = np.zeros(OUT)
        self.t = 0
        self.mW=np.zeros_like(self.W);  self.vW=np.zeros_like(self.W)
        self.mb=np.zeros_like(self.b);  self.vb=np.zeros_like(self.b)
        self.mWy=np.zeros_like(self.Wy); self.vWy=np.zeros_like(self.Wy)
        self.mby=np.zeros_like(self.by); self.vby=np.zeros_like(self.by)

    def forward(self, xs):
        h = np.zeros(H); c = np.zeros(H); cache = []
        for x in xs:
            xh = np.concatenate([x, h])
            z  = self.W @ xh + self.b
            ig = sigmoid(z[:H]);       fg = sigmoid(z[H:2*H])
            og = sigmoid(z[2*H:3*H]); gg = np.tanh(z[3*H:])
            cn = fg*c + ig*gg; tc = np.tanh(cn); hn = og*tc
            cache.append((x, h, c, xh, ig, fg, og, gg, cn, tc))
            h, c = hn, cn
        y = sigmoid(self.Wy @ h + self.by)
        return y, h, cache

    def train(self, xs, target, lr=3e-4, clip=5.0):
        y, h, cache = self.forward(xs)
        dy  = y - target
        dWy = np.outer(dy, h); dby = dy.copy()
        dh  = self.Wy.T @ dy;  dc  = np.zeros(H)
        dW  = np.zeros_like(self.W); db = np.zeros_like(self.b)
        for (x,hp,cp,xh,ig,fg,og,gg,cn,tc) in reversed(cache):
            do=dh*tc; dtc=dh*og; dc_tot=dtc*(1.0-tc**2)+dc
            di=dc_tot*gg; dg=dc_tot*ig; df=dc_tot*cp; dc=dc_tot*fg
            dz=np.concatenate([di*ig*(1-ig),df*fg*(1-fg),do*og*(1-og),dg*(1-gg**2)])
            dW+=np.outer(dz,xh); db+=dz; dh=(self.W.T@dz)[IN:]
        for g in (dW,db,dWy,dby): np.clip(g,-clip,clip,out=g)
        self.t+=1; t=self.t; b1,b2,eps=0.9,0.999,1e-8
        def adam(p,g,m,v):
            m[:]=b1*m+(1-b1)*g; v[:]=b2*v+(1-b2)*g**2
            p-=lr*(m/(1-b1**t))/(np.sqrt(v/(1-b2**t))+eps)
        adam(self.W,dW,self.mW,self.vW); adam(self.b,db,self.mb,self.vb)
        adam(self.Wy,dWy,self.mWy,self.vWy); adam(self.by,dby,self.mby,self.vby)

    def predict_scores(self, xs):
        y, _, _ = self.forward(xs)
        return y  # probability for each of 43 numbers

    def predict(self, xs, k=N_PICKS):
        y = self.predict_scores(xs)
        return [int(i+1) for i in np.argsort(y)[::-1][:k]]

    def to_dict(self):
        return {'W':self.W.tolist(),'b':self.b.tolist(),
                'Wy':self.Wy.tolist(),'by':self.by.tolist()}

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()
cur.execute("""
    SELECT draw_serial, draw_date, num1, num2, num3, num4, num5, num6, bonus
    FROM loto6_results ORDER BY draw_serial ASC
""")
rows = cur.fetchall(); conn.close()

draws = []
for s,d,n1,n2,n3,n4,n5,n6,bn in rows:
    draws.append({'serial':s,'date':str(d)[:10],
                  'nums':sorted([n1,n2,n3,n4,n5,n6]),'bonus':bn,
                  'all':set([n1,n2,n3,n4,n5,n6,bn])})

total = len(draws)
INIT_END = max(SEQ, total - BT_DRAWS)
print(f"Loaded {total} draws  INIT_END={INIT_END}  BT_DRAWS={BT_DRAWS}")

def to_vec(nums):
    v = np.zeros(IN)
    for n in nums: v[n-1] = 1.0
    return v

vecs = [to_vec(d['nums']) for d in draws]

lstm = LSTM()

# Phase 1: initial training
print(f"Phase 1 - training on {INIT_END} draws x 30 epochs...")
t0 = time.time()
for epoch in range(30):
    np.random.seed(epoch)
    idxs = np.random.permutation(range(SEQ, INIT_END))
    for i in idxs:
        lstm.train(vecs[i-SEQ:i], vecs[i])
    if (epoch+1) % 10 == 0:
        print(f"  epoch {epoch+1}/30  {time.time()-t0:.0f}s")
print(f"Phase 1 done {time.time()-t0:.1f}s")

# Phase 2: walk-forward backtest
print(f"\nPhase 2 - walk-forward backtest draws {INIT_END}..{total-1}...")
results = []; t1 = time.time()
for i in range(INIT_END, total):
    xs = vecs[i-SEQ:i]
    scores = lstm.predict_scores(xs)
    picks  = [int(j+1) for j in np.argsort(scores)[::-1][:N_PICKS]]
    actual_set = draws[i]['all']  # 7 numbers
    hits = sorted(actual_set & set(picks))
    results.append({
        'serial': draws[i]['serial'], 'date': draws[i]['date'],
        'actual': sorted(actual_set),
        'hitNums': hits, 'matches': len(hits),
        'pred': picks,
        'scores': [round(float(scores[j]),4) for j in np.argsort(scores)[::-1][:N_PICKS]]
    })
    lstm.train(xs, vecs[i])
    if len(results) % 200 == 0:
        print(f"  {len(results)} done  {time.time()-t1:.0f}s")

print(f"Phase 2 done {time.time()-t1:.1f}s - {len(results)} predictions")
mc = [r['matches'] for r in results]
print(f"Avg matches: {sum(mc)/len(mc):.4f}  rand baseline: {N_PICKS*7/43:.4f}")
print(f"6+ hits: {sum(1 for m in mc if m>=6)}/{len(mc)}")

# Phase 3: fine-tune on last 300 draws
print("\nPhase 3 - fine-tune last 300 draws x 10 epochs...")
t2 = time.time()
start3 = max(SEQ, total-300)
for epoch in range(10):
    np.random.seed(500+epoch)
    for i in np.random.permutation(range(start3, total)):
        lstm.train(vecs[i-SEQ:i], vecs[i])
print(f"Phase 3 done {time.time()-t2:.1f}s")

base = r"C:\Users\Zaw Min Htoon\source\repos\theonelotto"
with open(base + r"\lstm_weights.json", 'w') as f:
    json.dump(lstm.to_dict(), f, separators=(',',':'))
print("Saved lstm_weights.json")

with open(base + r"\lstm_backtest.json", 'w') as f:
    json.dump({'results': results, 'total': total,
               'initEnd': INIT_END, 'btDraws': BT_DRAWS,
               'nPicks': N_PICKS}, f, separators=(',',':'))
print(f"Saved lstm_backtest.json ({len(results)} entries)")

xs_final = vecs[-SEQ:]
final_scores = lstm.predict_scores(xs_final)
final_pred = [int(j+1) for j in np.argsort(final_scores)[::-1][:N_PICKS]]
final_score_list = [round(float(final_scores[j]),4) for j in np.argsort(final_scores)[::-1][:N_PICKS]]
print(f"\nNext draw prediction (top {N_PICKS}): {final_pred}")

with open(base + r"\lstm_next_pred.json", 'w') as f:
    json.dump({'serial': draws[-1]['serial']+1,
               'latestSerial': draws[-1]['serial'],
               'latestDate': draws[-1]['date'],
               'pred': final_pred, 'scores': final_score_list}, f, separators=(',',':'))
print("Saved lstm_next_pred.json")
