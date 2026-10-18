"""Write every layer's raw answer per photo -> benchmark/data/erp/slice_1_tooling/raw_layers_slice_1.csv"""
import csv
from pathlib import Path
R='/home/user/repos/almaham-3'
def load(f):
    try: return {r[0].strip():r[1].strip().upper().replace('\n',' ')[:40] for r in csv.reader(open(f)) if len(r)==2}
    except FileNotFoundError: return {}
L=[load(f'/tmp/opencode/{x}.csv') for x in ('vlm','vlm2','vlm3','vlm4')]
final={r['filename']:r['text'] for r in csv.DictReader(open(f'{R}/benchmark/data/erp/labels_slice_1.csv'))}
names=[Path(l.strip()).name for l in open(f'{R}/data/erp/slice_1_of_4.txt') if l.strip()]
with open(f'{R}/benchmark/data/erp/slice_1_tooling/raw_layers_slice_1.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['filename','pass1_enhanced','pass2_enhanced_strict','pass3_enhanced_careful','pass4_original_digitwise','final_label'])
    for n in names:
        if n in final: w.writerow([n]+[d.get(n,'') for d in L]+[final[n]])
