"""Forensic multi-hypothesis grid: 23 image variants (channels, inversion, CLAHE, retinex, de-glare inpaint, NLM, unsharp, gamma...) x readers v1/v2/v6, then cross-variant vote. Usage: python3 forensic_grid.py"""
import json,cv2,numpy as np,gt,paths,sevenseg as v1,sevenseg2 as v2,sevenseg6 as v6
from eval_sevenseg import DEV
lines=json.load(open(paths.LINE_BOXES))
def g3(x): x=np.clip(x,0,255).astype(np.uint8); return cv2.merge([x,x,x])
def retinex(im,s):
    f=im.astype(np.float32)+1; return g3(np.log(f.max(2))-np.log(cv2.GaussianBlur(f.max(2),(0,0),s))) if False else g3(cv2.normalize(np.log(f.max(2))-np.log(cv2.GaussianBlur(f.max(2),(0,0),s)),None,0,255,cv2.NORM_MINMAX))
def clahe(im,c):
    l=cv2.cvtColor(im,cv2.COLOR_BGR2LAB); l[...,0]=cv2.createCLAHE(c,(4,8)).apply(l[...,0]); return cv2.cvtColor(l,cv2.COLOR_LAB2BGR)
def deglare(im):
    m=im.max(2); hi=(m>np.percentile(m,97)).astype(np.uint8)*255
    return cv2.inpaint(im,cv2.dilate(hi,None),5,cv2.INPAINT_TELEA)
def unsharp(im): b=cv2.GaussianBlur(im,(0,0),2); return cv2.addWeighted(im,1.8,b,-0.8,0)
def gamma(im,g): return np.clip(255*((im/255.0)**g),0,255).astype(np.uint8)
def wb(im): f=im.astype(np.float32); f*=f.mean()/(f.reshape(-1,3).mean(0)+1); return np.clip(f,0,255).astype(np.uint8)
def sat_suppress(im):  # ghost segments are coloured (blue/grey); drop pixels with saturation toward background
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV); v=hsv[...,2].astype(np.float32); s=hsv[...,1].astype(np.float32)
    return g3(v+0.8*s)
def bilateral(im): return cv2.bilateralFilter(im,7,40,7)
def nlm(im): return cv2.fastNlMeansDenoisingColored(im,None,7,7,5,11)
def up2(im): return cv2.resize(im,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
V={"orig":lambda im:im,"gray":lambda im:g3(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)),
"R":lambda im:g3(im[...,2]),"G":lambda im:g3(im[...,1]),"B":lambda im:g3(im[...,0]),"min":lambda im:g3(im.min(2)),
"invert_x2":lambda im:255-(255-im),  # sanity
"clahe2":lambda im:clahe(im,2.0),"clahe4":lambda im:clahe(im,4.0),"retinex8":lambda im:retinex(im,8),"retinex30":lambda im:retinex(im,30),
"deglare":deglare,"unsharp":unsharp,"gamma0.6":lambda im:gamma(im,0.6),"gamma1.6":lambda im:gamma(im,1.6),"wb":wb,
"satsup":sat_suppress,"bilateral":bilateral,"nlm":nlm,"up2":up2,"deglare+clahe":lambda im:clahe(deglare(im),3.0),
"wb+clahe":lambda im:clahe(wb(im),3.0),"nlm+unsharp":lambda im:unsharp(nlm(im))}
data=[]
for it in gt.load():
    if not it.readable: continue
    im=cv2.imread(gt.PHOTOS+it.name);H,W=im.shape[:2];x1,y1,x2,y2=lines[it.name]
    data.append((it,im[int(y1*H):int(y2*H),int(x1*W):int(x2*W)]))
res={}
for vn,f in V.items():
    for rn,r in (("v1",v1),("v2",v2),("v6",v6)):
        okd=okh=0;outs={}
        for it,c in data:
            try: v,_,_=r.read_line(f(c))
            except Exception: v=""
            outs[it.name[:5]]=v
            if v==it.reading:
                if it.name[:5] in DEV: okd+=1
                else: okh+=1
        res[(vn,rn)]=outs
        print(f"{vn:14s} {rn} DEV {okd}/10 HOLD {okh}/36",flush=True)
truth={it.name[:5]:it.reading for it,_ in data}
for rn in ("v1","v2","v6"):
    any_ok=sum(1 for k in truth if any(res[(vn,rn)][k]==truth[k] for vn in V))
    print(rn,"ORACLE any-variant correct:",any_ok,"/46")
    # majority vote
    okv=wrong=empty=0
    for k in truth:
        from collections import Counter
        c=Counter(res[(vn,rn)][k] for vn in V if res[(vn,rn)][k])
        if not c: empty+=1; continue
        v,n=c.most_common(1)[0]
        if n<len(V)*0.4: empty+=1; continue
        if v==truth[k]: okv+=1
        else: wrong+=1
    print(rn,"VOTE(>=40%) ok",okv,"wrong",wrong,"empty",empty)
json.dump({f"{a}|{b}":v for (a,b),v in res.items()},open(paths.RESULTS_ENGINES/"grid_variants_lineL.json","w"),indent=0)
