import sys,json,os,re,base64,urllib.request,cv2,time
sys.path.insert(0,'/tmp'); from mt import c
from concurrent.futures import ThreadPoolExecutor,as_completed
P=("Classify the main electricity meter in this photo. Options: TOMAS_SMART (Tomas 'Bi-Directional Smart Meter', big grey LCD), "
"TOMAS_STATIC (Tomas 'Static kWh Meter', small yellow-green LCD), CRYSTAL (brand CRYSTAL, two-line LCD), TAGADOD (brand TAGADOD, blue backlit 7-digit LCD), "
"GLORY (brand Glory), KENWELL (Kenwell, green LCD), SMART_YELLOW (yellow-cased smart meter e.g. SMART MT10/DMC; also when its cover is open showing a green circuit board with green and red buttons), "
"EMETER_GREEN (green circuit board visible, other brand), HPL (three-phase HPL), MECHANICAL (drum counter), OTHER (any other brand - write the brand), NONE (no meter). "
"Reply exactly: TYPE: <option> BRAND: <brand text you can read or ?>")
def b64(p):
    im=cv2.imread(p); s=900/max(im.shape[:2]); im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode('.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,85])[1]).decode()
def ask(p):
    body={"model":"gpt-5.6-sol","messages":[{"role":"user","content":[{"type":"text","text":P},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(p)}}]}]}
    for i in range(4):
        try:
            r=urllib.request.Request(c['base_url']+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+c['api_key'],'Content-Type':'application/json'})
            t=json.loads(urllib.request.urlopen(r,timeout=180).read())['choices'][0]['message']['content']
            m=re.search(r'TYPE:\s*(\w+)',t); b=re.search(r'BRAND:\s*(.+)',t)
            return (m.group(1) if m else '?'), (b.group(1).strip() if b else '?')
        except Exception: time.sleep(5)
    return 'ERR','?'
