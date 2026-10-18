"""Append vision-model labels: python3 vlabel_add.py "<name1> <name2> ..." "<val1> <val2> ...". Writes data/erp/vlabels_raw.json."""
import json, sys, paths
ERP = paths.DATA / "erp"
p = ERP / "vlabels_raw.json"
d = json.load(open(p)) if p.exists() else {}
names, vals = sys.argv[1].split(), sys.argv[2].split()
assert len(names) == len(vals), (len(names), len(vals))
for n, v in zip(names, vals):
    d[n if n.endswith(".jpg") else n + ".jpg"] = v
json.dump(d, open(p, "w"), indent=0)
print(len(d), "labels total")
