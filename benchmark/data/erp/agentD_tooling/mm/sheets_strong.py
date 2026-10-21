import json,collections,cv2,numpy as np,os,sys,csv
sys.path.insert(0,'/tmp/mm'); from bbox import crop
R='/home/user/webapp/almaham-3/data/erp/photos/'
J=[json.loads(l) for l in open('/tmp/mm/strong.jsonl')]
by=collections.defaultdict(dict); T={}
for j in J:
    if j['ans']!='ERR' or j['m'] not in by[j['f']]: by[j['f']][j['m']]=j['ans']
    T[j['f']]=j['t']
lab=set(r['filename'] for r in csv.DictReader(open('/home/user/webapp/almaham-3/benchmark/data/erp/labels_agentD.csv')))
B={}
for l in open('/tmp/mm/boxes.jsonl'):
    j=json.loads(l)
    if isinstance(j['b'],list): B[j['f']]=j['b']
acc=[(f,list(v.values())[0],T[f]) for f,v in by.items() if len(v)==4 and len(set(v.values()))==1 and list(v.values())[0].isdigit() and f not in lab]
acc.sort(key=lambda x:x[2])
out='/tmp/mm/vs'; os.makedirs(out,exist_ok=True); idx=[]
for si in range(0,len(acc),9):
    tiles=[]
    for k,(f,a,t) in enumerate(acc[si:si+9]):
        b=B.get(f); im=crop(R+f,b) if b else cv2.imread(R+f)
        im=cv2.resize(im,(420,int(420*im.shape[0]/im.shape[1])))[:520]
        im=cv2.copyMakeBorder(im,32,520-im.shape[0],2,2,cv2.BORDER_CONSTANT); cv2.putText(im,f'#{si+k} {t[:8]} {a}',(5,25),0,.75,(0,255,255),2)
        tiles.append(im); idx.append((si+k,f,a,t))
    while len(tiles)%3: tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(f'{out}/{si//9:02d}.jpg',np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,len(tiles),3)]),[cv2.IMWRITE_JPEG_QUALITY,78])
csv.writer(open(f'{out}/index.csv','w'),lineterminator='\n').writerows(idx)
print(len(idx),(len(idx)+8)//9,collections.Counter(x[3] for x in idx))
