"""Debug view: CLAHE line crops with a 1/20 grid, or with digit_spans overlay (any arg). Writes /tmp/db_*.jpg."""
import json,cv2,numpy as np,gt,paths,csv,sys
lb=json.load(open(paths.LINE_BOXES))
dt={r["filename"]:r["display_text"] for r in csv.DictReader(open(paths.GROUND_TRUTH))}
spans=json.load(open(paths.REPO / 'benchmark/data/digit_spans_manual.json')) if len(sys.argv)>1 else {}
items=[it for it in gt.load() if it.readable]
tiles=[]
for it in items:
    im=cv2.imread(gt.PHOTOS+it.name);H,W=im.shape[:2];x1,y1,x2,y2=lb[it.name]
    c=im[int(y1*H):int(y2*H),int(x1*W):int(x2*W)]
    g=c.max(2);g=cv2.createCLAHE(3.0,(4,8)).apply(g);c=cv2.cvtColor(g,cv2.COLOR_GRAY2BGR)
    ch,cw=c.shape[:2];v=cv2.resize(c,(600,max(1,int(ch*600/cw))));vh=v.shape[0]
    if it.name in spans:
        a,b,cc,d,n=spans[it.name]
        for k in range(n):
            xa=a+(cc-a)*k/n; xb=a+(cc-a)*(k+1)/n
            cv2.rectangle(v,(int(xa*600)+1,int(b*vh)),(int(xb*600)-1,int(d*vh)),(0,255,0),1)
    else:
        for k in range(1,20):
            x=int(600*k/20);cv2.line(v,(x,0),(x,vh),(0,0,255) if k%2==0 else (0,0,140),1)
            if k%2==0: cv2.putText(v,str(k//2),(x+2,12),0,0.4,(0,0,255),1)
            y=int(vh*k/10) if k<10 else None
            if y: cv2.line(v,(0,y),(14,y),(255,128,0),2);cv2.putText(v,str(k),(16,y+4),0,0.4,(255,128,0),1)
    v=cv2.copyMakeBorder(v,18,0,0,0,cv2.BORDER_CONSTANT,value=(40,40,40))
    cv2.putText(v,f"{it.name[:5]} {dt[it.name]}",(4,13),0,0.45,(255,255,255),1)
    tiles.append(v)
for i in range(0,len(tiles),6):
    cv2.imwrite(f'/tmp/db_{i//6}.jpg',np.vstack([cv2.copyMakeBorder(t,0,4,0,0,cv2.BORDER_CONSTANT) for t in tiles[i:i+6]]))
