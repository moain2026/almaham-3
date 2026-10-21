import os,json,time,sys,subprocess
sys.path.insert(0,'/tmp/mm'); import importlib.util
spec=importlib.util.spec_from_file_location('cls','/tmp/mm/cls_lib.py'); cl=importlib.util.module_from_spec(spec); spec.loader.exec_module(cl)
from concurrent.futures import ThreadPoolExecutor
R='/home/user/webapp/almaham-3/data/erp/photos/'
lst=[l.split('\t')[0] for l in open('/tmp/mm/_div.txt')]
fn='/tmp/mm/cls_div.jsonl'; open(fn,'a').close()
done={json.loads(l)['f'] for l in open(fn)}
out=open(fn,'a'); ex=ThreadPoolExecutor(20); pend={}
def ok(p):
    try: return os.path.getsize(p)>20000 and b"\xff\xd9" in open(p,'rb').read()[-2048:]
    except: return False
while True:
    for f in lst:
        if f not in done and f not in pend and ok(R+f): pend[f]=ex.submit(cl.ask,R+f)
    for f,fu in list(pend.items()):
        if fu.done():
            t,b=fu.result(); out.write(json.dumps({'f':f,'t':t,'b':b})+'\n'); out.flush(); done.add(f); del pend[f]
    fetching=subprocess.run("pgrep -f fetch_div.py",shell=True,capture_output=True).stdout.strip()
    if not fetching and not pend and all(f in done or not ok(R+f) for f in lst): break
    time.sleep(5)
