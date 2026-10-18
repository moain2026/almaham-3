import csv
from pathlib import Path
def load(f):
    try: return {r[0]:r[1].strip().upper() for r in csv.reader(open(f)) if len(r)==2}
    except FileNotFoundError: return {}
a,b,c=[load(f'/tmp/opencode/{x}.csv') for x in ('vlm','vlm2','vlm3')]
names=[Path(l.strip()).name for l in open('/home/user/repos/almaham-3/data/erp/slice_1_of_4.txt') if l.strip()]
with open('/tmp/opencode/cand.txt','w') as f:
    for n in names:
        v=(a.get(n),b.get(n),c.get(n))
        if v[0] and v[0].isdigit() and v[0]==v[1]==v[2]: f.write(n+'\n')
