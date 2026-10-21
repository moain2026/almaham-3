import sys,json,os,re,subprocess,time,cv2
src=open('/tmp/mm/read_nt.py').read().split("MS=[")[0]; ns={}; exec(src,ns)
from concurrent.futures import ThreadPoolExecutor,as_completed
R='/home/user/webapp/almaham-3/data/erp/photos/'
def gem(f,t):
    pr=ns['P'].format(h=ns['HINT'].get(t,ns['HINT']['OTHER'])); p='/tmp/mm/gtmp_'+f
    im=cv2.imread(R+f); sc=1400/max(im.shape[:2]); im=cv2.resize(im,None,fx=sc,fy=sc) if sc<1 else im; cv2.imwrite(p,im,[cv2.IMWRITE_JPEG_QUALITY,88])
    for i in range(3):
        try:
            o=subprocess.run(['gsk','understand_images','-r',pr,'-i',p],capture_output=True,text=True,timeout=200).stdout
            x=json.loads(o)['data']['results'][0]['result']; mm=re.findall(r'ANSWER:\s*([0-9]+|X|P)',x,re.I)
            os.remove(p); return mm[-1].upper() if mm else 'X'
        except Exception: time.sleep(5)
    return 'ERR'
MS=['gpt-6.1-sol','gpt-6-astra','gemini','claude-opus-5-5']
jobs=[json.loads(l) for l in open(sys.argv[1])]
fn='/tmp/mm/strong.jsonl'; open(fn,'a').close()
done={(j['f'],j['m']) for j in map(json.loads,open(fn)) if j['ans']!='ERR'}
out=open(fn,'a')
with ThreadPoolExecutor(32) as ex:
    fu={}
    for j in jobs:
        for m in MS:
            if (j['f'],m) in done: continue
            fu[ex.submit(gem,j['f'],j['t']) if m=='gemini' else ex.submit(ns['ask'],m,j['f'],j['t'])]=(j,m)
    for x in as_completed(fu):
        j,m=fu[x]; out.write(json.dumps({'f':j['f'],'t':j['t'],'m':m,'ans':x.result()})+'\n'); out.flush()
