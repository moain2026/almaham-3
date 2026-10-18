import sys, json, subprocess, csv, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
names=[l.strip().split(',')[0] for l in open(sys.argv[1]) if l.strip()]
out=sys.argv[2]
done={r[0] for r in csv.reader(open(out))} if os.path.exists(out) else set()
P=("Original photo of an electricity meter. Find the main kWh display. Go digit by digit from left to right through the INTEGER part only "
"(stop at the decimal point; on 7-digit TAGADOD LCDs the last digit is a decimal; on drum counters skip the red drum). "
"For each digit check carefully which segments are really dark versus faint ghost segments: 0 vs 8, 1 vs 7, 3 vs 9, 5 vs 6 are common mistakes. "
"Count the digits: if the display shows more integer digits than usual, include them all. "
"If any digit is not certain answer X. If several meters and unclear which, answer P. "
"Final line must be: ANSWER: <digits or X or P>")
def job(n):
    if n in done: return None
    p=Path('/home/user/repos/almaham-3/data/erp/photos')/n
    im=cv2.imread(str(p))
    if im is None: return (n,'BADIMG')
    s=1600/max(im.shape[:2])
    if s<1: im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
    f=f'/tmp/opencode/orig/{n}'; os.makedirs('/tmp/opencode/orig',exist_ok=True); cv2.imwrite(f,im,[cv2.IMWRITE_JPEG_QUALITY,90])
    for _ in range(2):
        try:
            r=subprocess.run(['gsk','understand_images','-r',P,'-i',f],capture_output=True,text=True,timeout=150)
            t=json.loads(r.stdout)['data']['results'][0]['result']
            a=t.rsplit('ANSWER:',1)[-1].strip().split()[0].upper().strip('.`*') if 'ANSWER:' in t else 'X'
            return (n,a)
        except Exception: pass
    return (n,'ERR')
with ThreadPoolExecutor(16) as ex, open(out,'a',newline='') as fo:
    w=csv.writer(fo)
    for res in ex.map(job,names):
        if res: w.writerow(res); fo.flush()
