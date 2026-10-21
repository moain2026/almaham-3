import os,sys,yaml,json,base64,urllib.request,cv2,re,time
sys.path.insert(0,'/tmp'); from mt import c
P=("This photo shows an electricity meter. Find the ONE main meter (the one whose display is most central/largest). "
   "Return the bounding box of the WHOLE meter body (entire front plastic case including the LCD, brand label and serial-number sticker; NOT wires, NOT neighbouring meters). "
   "Coordinates as fractions 0..1 of image width/height. Reply exactly: BOX: x1 y1 x2 y2   (or BOX: NONE if no meter)")
def b64(im,mx=1024):
    s=mx/max(im.shape[:2]); im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode('.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,85])[1]).decode()
def box(path,model='gpt-5.6-sol'):
    im=cv2.imread(path)
    body={"model":model,"messages":[{"role":"user","content":[{"type":"text","text":P},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+b64(im)}}]}]}
    for i in range(4):
        try:
            r=urllib.request.Request(c['base_url']+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+c['api_key'],'Content-Type':'application/json'})
            t=json.loads(urllib.request.urlopen(r,timeout=180).read())['choices'][0]['message']['content']
            m=re.findall(r'BOX:\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',t)
            if m: return tuple(map(float,m[-1]))
            if 'NONE' in t.upper(): return None
        except Exception: time.sleep(5)
    return 'ERR'
def crop(path,b,pad=0.03,out=None):
    im=cv2.imread(path); H,W=im.shape[:2]
    x1,y1,x2,y2=b; x1=max(0,x1-pad);y1=max(0,y1-pad);x2=min(1,x2+pad);y2=min(1,y2+pad)
    cr=im[int(y1*H):int(y2*H),int(x1*W):int(x2*W)]
    if out: cv2.imwrite(out,cr,[cv2.IMWRITE_JPEG_QUALITY,90])
    return cr
