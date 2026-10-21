import json,collections,cv2,numpy as np,os,sys,csv
sys.path.insert(0,'/tmp/mm'); from bbox import crop
R='/home/user/webapp/almaham-3/data/erp/photos/'
J=[json.loads(l) for l in open('/tmp/mm/read_nt.jsonl')]
by=collections.defaultdict(dict); T={}
for j in J: by[j['f']][j['m']]=j['ans']; T[j['f']]=j['t']
B={}
for l in open('/tmp/mm/boxes.jsonl'):
    j=json.loads(l)
    if isinstance(j['b'],list): B[j['f']]=j['b']
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
seen=set()
if os.path.exists('/tmp/mm/nt_seen.txt'): seen=set(open('/tmp/mm/nt_seen.txt').read().split())
acc=[(f,list(v.values())[0],T[f]) for f,v in by.items() if len(v)==4 and len(set(v.values()))==1 and list(v.values())[0].isdigit() and f not in seen]
idx=[]
for si in range(0,len(acc),6):
    tiles=[]
    for k,(f,a,t) in enumerate(acc[si:si+6]):
        b=B.get(f); im=crop(R+f,b) if b else cv2.imread(R+f)
        im=cv2.resize(im,(500,int(500*im.shape[0]/im.shape[1])));im=im[:640]
        im=cv2.copyMakeBorder(im,32,640-im.shape[0],2,2,cv2.BORDER_CONSTANT); cv2.putText(im,f'#{si+k} {t}',(5,25),0,.8,(0,255,255),2)
        tiles.append(im); idx.append((si+k,f,a,t))
    while len(tiles)%3: tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(f'{out}/{si//6:02d}.jpg',np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,len(tiles),3)]),[cv2.IMWRITE_JPEG_QUALITY,80])
csv.writer(open(f'{out}/index.csv','w'),lineterminator='\n').writerows(idx)
open('/tmp/mm/nt_seen.txt','a').write('\n'.join(x[1] for x in idx)+'\n')
print(len(idx),(len(idx)+5)//6)
