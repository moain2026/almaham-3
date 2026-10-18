import cv2,json,time,sys,numpy as np
sys.path.insert(0, __import__('os').path.dirname(__file__))
import gt, sevenseg as S
d=json.load(open(str(__import__('paths').LINE_BOXES)))
items={i.name:i for i in gt.load()}
names=sys.argv[1].split(',') if len(sys.argv)>1 else ['23066','23113','23070','23082']
rows=[]
for f in names:
    it=items[f+'.jpg']; im=cv2.imread(gt.PHOTOS+it.name);H,W=im.shape[:2];x1,y1,x2,y2=d[it.name]
    c=im[int(y1*H):int(y2*H),int(x1*W):int(x2*W)]
    t=time.perf_counter(); v,cf,info=S.read_line(c); ms=(time.perf_counter()-t)*1000
    print(f,'truth',it.reading,'got',v,'OK' if v==it.reading else 'X',info.get('raw'),[round(x,2) for x in cf],f'{ms:.1f}ms')
    m,_=S.deskew(S.clean_mask(S.ink_map(c))); vv=cv2.cvtColor(m*255,cv2.COLOR_GRAY2BGR)
    for b in S.digit_boxes(m):
        x,y,w,h=b; cv2.rectangle(vv,(x,y),(x+w,y+h),(0,0,255),1)
    rows.append(cv2.resize(vv,(600,int(vv.shape[0]*600/vv.shape[1])),interpolation=cv2.INTER_NEAREST))
cv2.imwrite(str(__import__('paths').REVIEW / 'sevenseg_debug.jpg'),np.vstack(rows))
