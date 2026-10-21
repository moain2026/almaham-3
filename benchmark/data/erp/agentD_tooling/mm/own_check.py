import sys,json,os,re,base64,urllib.request,cv2,time,csv
sys.path.insert(0,'/tmp'); from mt import c
from concurrent.futures import ThreadPoolExecutor,as_completed
R='/home/user/webapp/almaham-3/data/erp/photos/'
HINT={'SMART_YELLOW':"Yellow smart meter (Iraqi/MT10/DMC); if the cover is open a green circuit board is visible - the reading is on its LCD: 6 integer digits then decimals.",
'MECHANICAL':"Mechanical drum counter: report ONLY the black/white integer drums, skip the red (or last differently coloured) decimal drum. If a drum is between two numbers answer X.",
'KENWELL':"Kenwell meter with green electronic LCD: report the kWh integer part (before the decimal point/last small digit).",
'HPL':"Three-phase HPL meter: report the integer kWh total.",
'GLORY':"Glory meter: report the integer kWh part before the decimal point.",
'CHINT':"CHINT meter (often mechanical drums): report only the integer drums, skip the red decimal drum.",
'CRYSTAL':"CRYSTAL two-line LCD: read ONLY the upper big kWh line, integer part before the dot (e.g. 46.12 -> 46, 355.70 -> 355, 1247.3 -> 1247). Do NOT add leading zeros.",
'TAGADOD':"TAGADOD blue backlit LCD with 7 equal digits: the LAST digit is a decimal - drop it and report the first 6.",
'OTHER':"Report the integer kWh part before the decimal point; skip red decimal drum if mechanical."}
P=("Electricity meter photo. {h} Read the main kWh reading INTEGER part exactly as displayed (keep displayed leading zeros, no decimals). "
   "Check ghost segments (0/8,1/7,3/9,5/6). If ANY integer digit is uncertain answer X. If several meters and unclear which, answer P. Final line exactly: ANSWER: <digits or X or P>")
def b64(p):
    im=cv2.imread(p); s=1400/max(im.shape[:2])
    if s<1: im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode('.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,88])[1]).decode()
def ask(m,f,t):
    body={"model":m,"messages":[{"role":"user","content":[{"type":"text","text":P.format(h=HINT.get(t,HINT['OTHER']))},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(R+f)}}]}]}
    for i in range(5):
        try:
            r=urllib.request.Request(c['base_url']+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+c['api_key'],'Content-Type':'application/json'})
            x=json.loads(urllib.request.urlopen(r,timeout=240).read())['choices'][0]['message']['content'].split('</think>')[-1]
            mm=re.findall(r'ANSWER:\s*([0-9]+|X|P)',x,re.I)
            return mm[-1].upper() if mm else 'X'
        except Exception: time.sleep(5*(i+1))
    return 'ERR'
MS=['gpt-6.1-sol','gpt-6-astra']
jobs=[json.loads(l) for l in open(sys.argv[1])]   # {f,t}
fn='/tmp/mm/own_check.jsonl'; open(fn,'a').close()
done={(j['f'],j['m']) for j in map(json.loads,open(fn)) if j['ans']!='ERR'}
out=open(fn,'a')
with ThreadPoolExecutor(32) as ex:
    fu={ex.submit(ask,m,j['f'],j['t']):(j,m) for j in jobs for m in MS if (j['f'],m) not in done}
    for x in as_completed(fu):
        j,m=fu[x]; out.write(json.dumps({'f':j['f'],'t':j['t'],'m':m,'ans':x.result()})+'\n'); out.flush()
