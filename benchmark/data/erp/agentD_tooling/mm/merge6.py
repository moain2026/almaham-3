import csv,json,sys,time,cv2,hashlib
sys.path.insert(0,'/tmp/mm'); from bbox import crop
PUB='/home/user/webapp/almaham-3/benchmark/data/erp/'
PRV='/home/user/webapp/almaham-3-private-data/erp/'
R=PRV+'photos/'
TEST=set(l.split()[0] for l in open('/home/user/webapp/almaham-3/benchmark/data/photos.sha256') if l.strip())
rej=set(int(x) for x in open('vs_rej.txt').read().split())
fix={int(a):b for a,b in (l.split() for l in open('vs_type.txt') if l.strip())}
B={}
for l in open('boxes.jsonl'):
    d=json.loads(l); B[d['f']]=d['b']
rows=list(csv.reader(open(PUB+'labels_agentD.csv')))
have=set(r[0] for r in rows[1:])
rejf=set(r[0] for r in csv.reader(open(PUB+'labels_agentD_rejected.csv')))
ts=int(time.time()); add=[]; skip={'rej':0,'dup':0,'test':0}
for k,f,rd,t in csv.reader(open('vs/index.csv')):
    k=int(k)
    if k in rej: skip['rej']+=1; continue
    if f in have or f in rejf: skip['dup']+=1; continue
    if hashlib.sha256(open(R+f,'rb').read()).hexdigest() in TEST: skip['test']+=1; continue
    t=fix.get(k,t)
    if t=='SMART_YE': t='SMART_YELLOW'
    add.append([f,rd,'agentD',str(ts),'4',t,'4strong+visual',''])
print(len(add),skip)
from collections import Counter; print(Counter(a[5] for a in add))
if '--go' in sys.argv:
    with open(PUB+'labels_agentD.csv','a',newline='') as fo:
        w=csv.writer(fo,lineterminator='\n'); w.writerows(add)
    import os
    for a in add:
        f,rd,t=a[0],a[1],a[5]; d=PRV+'by_type/'+t+'/'; os.makedirs(d,exist_ok=True)
        b=B.get(f); im=crop(R+f,b) if b else cv2.imread(R+f)
        cv2.imwrite(d+f,im,[cv2.IMWRITE_JPEG_QUALITY,92])
        new=not os.path.exists(d+'index.csv')
        with open(d+'index.csv','a',newline='') as fo:
            w=csv.writer(fo,lineterminator='\n')
            if new: w.writerow(['filename','reading','labeller','source','crop'])
            w.writerow([f,rd,'agentD','4strong+visual','full_meter' if b else 'none'])
    print('done')
