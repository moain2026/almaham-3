import csv, sys, time
from pathlib import Path
N=int(sys.argv[1])
def load(f):
    d={}
    for r in csv.reader(open(f)):
        if len(r)==2:
            t=r[1].strip().upper()
            d[r[0]]=t if (t.isdigit() or t in ('X','P')) else 'X'
    return d
a,b,c,d4=[load(f'/tmp/opencode/{x}.csv') for x in ('vlm','vlm2','vlm3','vlm4')]
names=[Path(l.strip()).name for l in open('/home/user/repos/almaham-3/data/erp/slice_1_of_4.txt') if l.strip()][:N]
ts=int(time.time()); out=[]; miss=0
for n in names:
    v=[d.get(n) for d in (a,b,c)]
    if None in v: miss+=1; continue
    if v[0] in ('SKIP_TEST','BADIMG'): continue
    t=v[0] if v[0]==v[1]==v[2] else 'X'
    if t.isdigit():
        if n not in d4: miss+=1; continue
        if d4[n]!=t: t='X'
    out.append((n,t,'labeller_1',ts))
Path('/home/user/repos/almaham-3/data/erp/labels').mkdir(parents=True,exist_ok=True)
with open(f'/home/user/repos/almaham-3/data/erp/labels/labeller_1_{N:04d}.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['filename','text','labeller','ts']); w.writerows(out)
print('rows',len(out),'missing',miss)
