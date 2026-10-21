import sys,json,random,csv,os,re,subprocess,time
sys.path.insert(0,'/tmp/mm'); import importlib.util
s=importlib.util.spec_from_file_location('r','/tmp/mm/read_nt.py')
src=open('/tmp/mm/read_nt.py').read().split("MS=[")[0]; ns={}; exec(src,ns)
from concurrent.futures import ThreadPoolExecutor,as_completed
R='/home/user/webapp/almaham-3/'
rows=[r for r in csv.DictReader(open(R+'benchmark/data/erp/labels_agentD.csv')) if r['labeller']=='owner' and not r['meter_type'].startswith('TOMAS')]
random.seed(9); rows=random.sample(rows,48)
def gem(f,t):
    pr=ns['P'].format(h=ns['HINT'].get(t,ns['HINT']['OTHER']))
    p='/tmp/mm/g_'+f; 
    import cv2; im=cv2.imread(R+'data/erp/photos/'+f); sc=1400/max(im.shape[:2]); im=cv2.resize(im,None,fx=sc,fy=sc) if sc<1 else im; cv2.imwrite(p,im,[cv2.IMWRITE_JPEG_QUALITY,88])
    for i in range(3):
        try:
            o=subprocess.run(['gsk','understand_images','-r',pr,'-i',p],capture_output=True,text=True,timeout=200).stdout
            x=json.loads(o)['data']['results'][0]['result']; mm=re.findall(r'ANSWER:\s*([0-9]+|X|P)',x,re.I)
            os.remove(p); return mm[-1].upper() if mm else 'X'
        except Exception: time.sleep(5)
    return 'ERR'
MS=sys.argv[1:]
out=open('/tmp/mm/bench3.jsonl','a')
with ThreadPoolExecutor(24) as ex:
    fu={}
    for r in rows:
        for m in MS:
            fu[ex.submit(gem if m=='gemini' else ns['ask'],*( (r['filename'],r['meter_type']) if m=='gemini' else (m,r['filename'],r['meter_type'])))]=(r,m)
    for x in as_completed(fu):
        r,m=fu[x]; out.write(json.dumps({'f':r['filename'],'t':r['meter_type'],'gt':r['owner_raw'] or r['text'],'m':m,'ans':x.result()})+'\n'); out.flush()
