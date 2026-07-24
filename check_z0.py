import json, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
with open(r'C:\Users\Zaw Min Htoon\source\repos\theonelotto\public\combo_evo_data.json') as f:
    D = json.load(f)

methods = D['methods']
combos = D['combos']

for K in ('15', '20'):
    rows = [(k, v[K]) for k, v in combos.items()]
    by_z0 = sorted(rows, key=lambda x: x[1]['dist'][0])
    print('K=' + K + ' -- fewest 0-hit draws:')
    for k, v in by_z0[:5]:
        m0, m1 = map(int, k.split(','))
        z0 = v['dist'][0]
        avg = v['avg']
        fp = v['fp']
        dist = v['dist']
        print('  ' + methods[m0] + ' + ' + methods[m1] + ': z0=' + str(z0) + ', avg=' + str(avg) + ', 4+=' + str(fp) + ', dist=' + str(dist))
    print('  ...most 0-hit:')
    for k, v in by_z0[-3:]:
        m0, m1 = map(int, k.split(','))
        z0 = v['dist'][0]
        print('  ' + methods[m0] + ' + ' + methods[m1] + ': z0=' + str(z0) + ', avg=' + str(v['avg']))
    print()
