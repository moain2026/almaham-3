import csv,json,sys,cv2,numpy as np
import paths, assemble
from eval_e2e import Engine, PAD_X, PAD_Y, RD_W, RD_H, RD_PEAK_MIN, letterbox
from det_model import decode
eng=Engine(sys.argv[1])
gt={r["filename"]:r for r in csv.DictReader(open(paths.GROUND_TRUTH,encoding="utf-8"))}
lines=json.load(open(paths.LINE_BOXES))
files=sys.argv[2:] or sorted(f for f in gt if gt[f]["reading"] and f in lines)
stats={"n":0,"exact_digits_seq":0,"int_boundary_wrong":0,"subst":0,"missing":0,"extra":0}
for fn in files:
    if fn not in lines: continue
    g=gt[fn]; truth=g["reading"]; disp=g.get("display_text","")
    im=cv2.imread(paths.photo(fn)); H,W=im.shape[:2]
    lx1,ly1,lx2,ly2=lines[fn]; lw,lh=(lx2-lx1)*W,(ly2-ly1)*H
    crop=im[int(max(0,ly1*H-PAD_Y*lh)):int(min(H,ly2*H+PAD_Y*lh)), int(max(0,lx1*W-PAD_X*lw)):int(min(W,lx2*W+PAD_X*lw))]
    ri,_,_,_=letterbox(crop,RD_W,RD_H,centre_x=False)
    peaks,size,offs=eng.run(eng.rd,ri)
    dets=decode(peaks,size,offs,RD_PEAK_MIN)
    dg=sorted([d for d in dets if d[0]<10],key=lambda d:(d[2]+d[4])/2)
    seq="".join(str(d[0]) for d in dg)
    hs=[round(d[5]-d[3]) for d in dg]; sc=[round(d[1],2) for d in dg]
    r=assemble.assemble(dets,RD_W,RD_H)
    # truth integer with leading zeros as displayed: display_text digits only
    tdisp="".join(ch for ch in disp if ch.isdigit())
    stats["n"]+=1
    tag=""
    if tdisp and seq==tdisp: stats["exact_digits_seq"]+=1; tag="ALLDIGITS_OK" + ("" if r.value==truth else " -> BOUNDARY_WRONG")
    if tdisp and seq==tdisp and r.value!=truth: stats["int_boundary_wrong"]+=1
    print(f"{fn} {g['meter_type']:12s} gt={truth:6s} disp={disp:10s} seq={seq:10s} h={hs} asm={r.value:7s} {r.status:7s} {tag}")
    if dg: print("     scores",sc)
print(stats)
