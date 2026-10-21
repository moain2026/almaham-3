import json,csv,collections,time,os,sys,cv2
sys.path.insert(0,'/tmp/mm'); from bbox import crop
PUB='/home/user/webapp/almaham-3/benchmark/data/erp/'; PRV='/home/user/webapp/almaham-3-private-data/erp/'; R=PRV+'photos/'
L=json.load(open('/tmp/agD/h7/owner_labels.json'))['labels']
S=collections.defaultdict(dict)
for l in open('strong.jsonl'):
    d=json.loads(l); S[d['f']][d['m']]=d['ans']
FIX={1:'07722',2:'07193',5:'15853',9:'00479'}           # owner typed the red decimal drum too
TFIX={3:'CRYSTAL',46:'OTHER'}
B={}
for l in open('boxes.jsonl'):
    j=json.loads(l)
    if isinstance(j['b'],list): B[j['f']]=j['b']
have=set(r[0] for r in csv.reader(open(PUB+'labels_agentD.csv')))|set(r[0] for r in csv.reader(open(PUB+'labels_agentD_rejected.csv')))
ts=str(int(time.time())); acc=[]; rej=[]
for l in sorted(L,key=lambda x:x['n']):
    f=l['filename']; r=l['reading']; t=TFIX.get(l['n'],l['type'].split(':')[0])
    if f in have: continue
    if r in('X','P'):
        rej.append([f,r,'owner',ts,'1',t,r,r]); continue
    txt=FIX.get(l['n'],r)
    m=[a for a in S.get(f,{}).values() if a.isdigit() and (a.lstrip('0') or '0')==(txt.lstrip('0') or '0')]
    if m: txt=max(m,key=len)
    acc.append([f,txt,'owner',ts,'1',t,'owner_visual',r])
print('acc',len(acc),'rej',len(rej),collections.Counter(a[5] for a in acc))
for a in acc: print(a[1],a[7],a[5])
if '--go' in sys.argv:
    w=csv.writer(open(PUB+'labels_agentD.csv','a',newline=''),lineterminator='\n'); w.writerows(acc)
    w=csv.writer(open(PUB+'labels_agentD_rejected.csv','a',newline=''),lineterminator='\n'); w.writerows(rej)
    for a in acc:
        f,t=a[0],a[5]; d=PRV+'by_type/'+t+'/'; os.makedirs(d,exist_ok=True); b=B.get(f)
        cv2.imwrite(d+f,crop(R+f,b) if b else cv2.imread(R+f),[cv2.IMWRITE_JPEG_QUALITY,92])
        new=not os.path.exists(d+'index.csv')
        with open(d+'index.csv','a',newline='') as fo:
            ww=csv.writer(fo,lineterminator='\n')
            if new: ww.writerow(['filename','reading','labeller','source','crop'])
            ww.writerow([f,a[1],'owner','owner_visual (المالك بنفسه)','full_meter' if b else 'none'])
    print('written')
