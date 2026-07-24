import json, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
with open(r'C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_data.json') as f:
    D = json.load(f)

methods = D['methods']
combos = D['combos']

for K in ('15', '20'):
    rows = [(k, v[K]) for k, v in combos.items()]
    by_z6 = sorted(rows, key=lambda x: x[1]['dist'][6], reverse=True)
    by_z0 = sorted(rows, key=lambda x: x[1]['dist'][0], reverse=True)
    print('K=' + K + ' -- most 6-hit draws (best):')
    for k, v in by_z6[:5]:
        m0, m1 = map(int, k.split(','))
        z6 = v['dist'][6]
        z0 = v['dist'][0]
        avg = v['avg']
        dist = v['dist']
        print('  ' + methods[m0] + ' + ' + methods[m1] + ': 6-hit=' + str(z6) + ', 0-hit=' + str(z0) + ', avg=' + str(avg))
    print()
    print('K=' + K + ' -- most 0-hit draws (worst):')
    for k, v in by_z0[:5]:
        m0, m1 = map(int, k.split(','))
        z6 = v['dist'][6]
        z0 = v['dist'][0]
        avg = v['avg']
        print('  ' + methods[m0] + ' + ' + methods[m1] + ': 0-hit=' + str(z0) + ', 6-hit=' + str(z6) + ', avg=' + str(avg))
    print()
