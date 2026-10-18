import sys, json, subprocess, csv, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,'.')
import cv2, erp_label
names=[Path(l.strip()).name for l in open('../data/erp/slice_1_of_4.txt') if l.strip()]
os.makedirs('/tmp/opencode/enh',exist_ok=True)
out='/tmp/opencode/vlm3.csv'
done={r[0] for r in csv.reader(open(out))} if os.path.exists(out) else set()
P=("You are a careful data labeller. Look at the electricity meter's main LCD (or mechanical counter) and write the integer kWh reading exactly as displayed, keeping leading zeros. "
"Do not include decimal digits: on Tomas meters these are the small digits after the dot; on TAGADOD meters the 7th digit after the dot; on drum counters the red drum. Ignore secondary lines, voltages and serial numbers. "
"Output X if even one integer digit is not certain or the display is unreadable; output P if several meters are visible and which one is meant is unclear. Output ONLY the digits, X or P, with no explanation.")
def job(n):
    if n in done: return None
    p=Path('../data/erp/photos')/n
    if not p.exists(): return None
    if erp_label.is_test_photo(p): return (n,'SKIP_TEST')
    img=cv2.imread(str(p))
    if img is None: return (n,'BADIMG')
    f=f'/tmp/opencode/enh/{n}'; open(f,'wb').write(erp_label.enhanced_view(img))
    for _ in range(2):
        try:
            r=subprocess.run(['gsk','understand_images','-r',P,'-i',f],capture_output=True,text=True,timeout=120)
            t=json.loads(r.stdout)['data']['results'][0]['result'].strip().upper()
            return (n,t)
        except Exception as e: err=str(e)
    return (n,'ERR')
with ThreadPoolExecutor(16) as ex, open(out,'a',newline='') as fo:
    w=csv.writer(fo)
    for res in ex.map(job,names):
        if res: w.writerow(res); fo.flush()
