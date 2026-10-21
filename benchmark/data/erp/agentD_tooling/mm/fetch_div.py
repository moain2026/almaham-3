import json,csv,glob,os,random,subprocess,sys,collections
sys.path.insert(0,'/home/user/webapp/almaham-3/lab'); import paths
N=int(sys.argv[1]); par=int(sys.argv[2])
out=paths.DATA/"erp"/"photos"
lab=set()
for f in glob.glob(str(paths.BENCH_DATA/"erp"/"labels*.csv")):
    for r in csv.DictReader(open(f)): lab.add(r["filename"])
where={}
for c in ("Mabar","Hodeidah"):
    for x in json.load(open(paths.DATA/"erp"/"manifests"/f"{c}-files.json")):
        if "/meter-readings/" in x["path"] and x["path"].endswith(".jpg"): where[x["path"].rsplit("/",1)[-1]]=x["path"]
W={'045458fdcdef':4,'2599580ba7c4':3.5,'e51747035754':3,'60ec43671a60':3,'3cccd8aaf5c9':2.6,'1bbcc05cf3e0':2.5,'26b9108e73cf':2.4,'bae9067d09e5':2.3,'814342b2779c':2.2,'e09cc36496cb':2}
cand=[f for f in where if f not in lab and not (out/f).exists()]
rnd=random.Random(21)
def w(f): return W.get(where[f].split('/')[3][-12:],1.0)
cand.sort(key=lambda f:-w(f)*rnd.random())
batch=cand[:N]
lst='/tmp/mm/_div.txt'; open(lst,'w').write("".join(f"{fn}\t{where[fn]}\n" for fn in batch))
auth=f"{os.environ['ERP_USER']}:{os.environ['ERP_PASS']}"
subprocess.run(f"cat {lst} | xargs -P {par} -L 1 sh -c 'curl -s -f --max-time 300 -u \"$0\" -o \"{out}/$1\" \"https://photos.alabasi.uk/$2\"' \"{auth}\"",shell=True)
got=[]
for fn in batch:
    p=out/fn
    if p.exists() and (p.stat().st_size<=20000 or b"\xff\xd9" not in open(p,"rb").read()[-2048:]): p.unlink()
    elif p.exists(): got.append(fn)
with open(paths.DATA/"erp"/"manifests"/"fetched_any.csv","a",newline="") as f:
    wr=csv.writer(f,lineterminator="\n")
    for fn in got: wr.writerow([fn,where[fn]])
open('/tmp/mm/new_div.txt','a').write("".join(fn+"\n" for fn in got))
print("got",len(got),"/",len(batch))
