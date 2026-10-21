import json,os,sys,cv2,csv,collections,secrets,shutil
sys.path.insert(0,'/tmp/mm'); from bbox import crop
R='/home/user/webapp/almaham-3-private-data/erp/photos/'; H='/tmp/agD/h7'
os.makedirs(H+'/img',exist_ok=True)
pub='/home/user/webapp/almaham-3/benchmark/data/erp/'
done=set(r[0] for r in csv.reader(open(pub+'labels_agentD.csv')))|set(r[0] for r in csv.reader(open(pub+'labels_agentD_rejected.csv')))
TEST=set(l.split()[0] for l in open('/home/user/webapp/almaham-3/benchmark/data/photos.sha256') if l.strip())
import hashlib
T={}
for fn in ('cls.jsonl','cls_div.jsonl','cls_re.jsonl'):
    if os.path.exists(fn):
        for l in open(fn):
            j=json.loads(l)
            if j['t'] not in('?','ERR') or j['f'] not in T: T[j['f']]=j
def typ(f,dflt='OTHER'):
    j=T.get(f)
    if not j: return dflt
    t={'EMETER_GREEN':'SMART_YELLOW','SMART_MT10':'SMART_YELLOW'}.get(j['t'],j['t'])
    return 'CHINT' if 'CHINT' in j.get('b','').upper() else t
src=[]
idx={int(k):(f,t) for k,f,_,t in csv.reader(open('vs/index.csv'))}
fix={int(a):b for a,b in (l.split() for l in open('vs_type.txt') if l.strip())}
for k in sorted(set(int(x) for x in open('vs_rej.txt').read().split())):
    f,t=idx[k]; src.append((f,fix.get(k,t).replace('SMART_YE','SMART_YELLOW') if fix.get(k,t)!='SMART_YELLOW' else 'SMART_YELLOW'))
for f in json.load(open('h4_bad43.json'))+json.load(open('owner_doubt.json')): src.append((f,typ(f)))
for i in json.load(open('/tmp/agD/h6/items.json')): src.append((i['filename'],i['type']))
for l in open('strong.jsonl'):
    d=json.loads(l); src.append((d['f'],typ(d['f'],d.get('t') or 'OTHER')))
seen=set(); items=[]
B={}
for l in open('boxes.jsonl'):
    j=json.loads(l)
    if isinstance(j['b'],list): B[j['f']]=j['b']
for f,t in src:
    if f in seen or f in done or not os.path.exists(R+f): continue
    if hashlib.sha256(open(R+f,'rb').read()).hexdigest() in TEST: continue
    seen.add(f); items.append({'filename':f,'type':t})
order=['CHINT','HPL','MECHANICAL','GLORY','KENWELL','CRYSTAL','SMART_YELLOW','TAGADOD']
items.sort(key=lambda i:order.index(i['type'].split(':')[0]) if i['type'].split(':')[0] in order else 99)
for n,it in enumerate(items,1):
    it['n']=n; f=it['filename']; b=B.get(f)
    im=crop(R+f,b) if b and (b[2]-b[0])>0.15 and (b[3]-b[1])>0.15 else cv2.imread(R+f)
    s=1100/max(im.shape[:2]); im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_AREA) if s<1 else im
    cv2.imwrite(f'{H}/img/{n}.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,80])
    o=cv2.imread(R+f); s=1400/max(o.shape[:2]); cv2.imwrite(f'{H}/img/{n}_o.jpg',cv2.resize(o,None,fx=s,fy=s,interpolation=cv2.INTER_AREA),[cv2.IMWRITE_JPEG_QUALITY,75])
json.dump(items,open(H+'/items.json','w'))
shutil.copy('/tmp/agD/h6/server.py',H+'/server.py')
open(H+'/token','w').write(secrets.token_urlsafe(12))
json.dump({'saved_at':'','labels':[]},open(H+'/owner_labels.json','w'))
print(len(items),collections.Counter(i['type'].split(':')[0] for i in items))
