import sys, json, subprocess, csv, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,'.')
import cv2, erp_label
names=[Path(l.strip()).name for l in open('../data/erp/slice_1_of_4.txt') if l.strip()]
os.makedirs('/tmp/opencode/enh',exist_ok=True)
out='/tmp/opencode/vlm.csv'
done={r[0] for r in csv.reader(open(out))} if os.path.exists(out) else set()
P=("This is an enlarged photo of an electricity meter. Read ONLY the large integer digits of the main LCD reading, exactly as displayed including leading zeros. "
"Ignore small fraction digits after the decimal point and any serial numbers. If any single digit is uncertain (glare, ghost segments, blur, cut off), answer X. "
"If the display is unreadable or there is no meter display answer X. If several meters are shown and the target is unclear answer P. Answer with only the digits, or X, or P.")
def job(n):
    if n in done: return None
    p=Path('../data/erp/photos')/n
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
with ThreadPoolExecutor(8) as ex, open(out,'a',newline='') as fo:
    w=csv.writer(fo)
    for res in ex.map(job,names):
        if res: w.writerow(res); fo.flush()
