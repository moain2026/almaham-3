import json,os,sys,cv2,collections,csv
sys.path.insert(0,'/tmp/mm'); from bbox import box,crop
from concurrent.futures import ThreadPoolExecutor
R='/home/user/webapp/almaham-3/data/erp/photos/'; H=sys.argv[1]
os.makedirs(H+'/img',exist_ok=True)
items=json.load(open(H+'/items.json')) if os.path.exists(H+'/items.json') else []
have={i['filename'] for i in items}
lab=set()
for f in ('benchmark/data/erp/labels_agentD.csv','benchmark/data/erp/labels_agentD_rejected.csv'):
    for r in csv.DictReader(open(f)): lab.add(r['filename'])
T={}
for fn in ('cls.jsonl','cls_div.jsonl','cls_re.jsonl'):
    p='/tmp/mm/'+fn
    if os.path.exists(p):
        for l in open(p):
            j=json.loads(l)
            if j['t'] not in('?','ERR') or j['f'] not in T: T[j['f']]=j
MAP={'EMETER_GREEN':'SMART_YELLOW'}
def typ(j):
    t=MAP.get(j['t'],j['t']); b=j['b'].upper()
    if 'CHINT' in b: return 'CHINT'
    return t
order=['CHINT','HPL','MECHANICAL','CRYSTAL','GLORY','KENWELL','SMART_YELLOW','OTHER','TAGADOD']
new=[(f,typ(j),j['b']) for f,j in T.items() if f not in lab and f not in have and typ(j) in order and os.path.exists(R+f)]
new.sort(key=lambda x:order.index(x[1]))
B={}
for l in open('/tmp/mm/boxes.jsonl'):
    j=json.loads(l)
    if isinstance(j['b'],list): B[j['f']]=j['b']
need=[x for x in new if x[0] not in B]
with ThreadPoolExecutor(24) as ex:
    for (f,_,_),b in zip(need,ex.map(lambda x:box(R+x[0]),need)):
        if isinstance(b,tuple): B[f]=list(b); open('/tmp/mm/boxes.jsonl','a').write(json.dumps({'f':f,'b':b})+'\n')
n=len(items)
for f,t,br in new:
    n+=1; b=B.get(f)
    im=crop(R+f,b) if b and (b[2]-b[0])>0.15 and (b[3]-b[1])>0.15 else cv2.imread(R+f)
    s=1100/max(im.shape[:2]); im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_AREA) if s<1 else im
    cv2.imwrite(f'{H}/img/{n}.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,80])
    o=cv2.imread(R+f); s=1400/max(o.shape[:2]); cv2.imwrite(f'{H}/img/{n}_o.jpg',cv2.resize(o,None,fx=s,fy=s,interpolation=cv2.INTER_AREA),[cv2.IMWRITE_JPEG_QUALITY,75])
    items.append({'n':n,'filename':f,'type':t if t!='OTHER' else 'OTHER:'+br[:20]})
json.dump(items,open(H+'/items.json','w'))
print('added',len(new),'total',len(items),collections.Counter(x[1] for x in new))
