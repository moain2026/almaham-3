"""Owner labelling page v2 (phone): one photo at a time, fixed bottom panel (input, X, P, save, prev/next).
Customer photos -> every route needs the secret token in the path. Saves to owner_labels.json (+timestamped copies)."""
import json, os, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

D = os.path.dirname(os.path.abspath(__file__))
TOK = open(f"{D}/token").read().strip()
ITEMS = json.load(open(f"{D}/items.json"))
OUT = f"{D}/owner_labels.json"

PAGE = r"""<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<title>قراءات</title>
<style>
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#000;color:#eee;font-family:system-ui,Tahoma}
#top{position:fixed;top:0;left:0;right:0;height:34px;background:#111;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:14px;z-index:5}
#num{color:#ffd54f;font-weight:bold}#st{color:#8f8;font-size:12px}
#view{position:fixed;top:34px;left:0;right:0;bottom:var(--ph,190px);overflow:auto;-webkit-overflow-scrolling:touch;touch-action:pan-x pan-y pinch-zoom}
#view img{display:block;width:100%;height:auto}
#panel{position:fixed;left:0;right:0;bottom:0;background:#1b1b1b;border-top:2px solid #444;padding:8px 8px calc(8px + env(safe-area-inset-bottom));z-index:6}
#val{width:100%;font-size:32px;padding:6px 8px;direction:ltr;text-align:center;letter-spacing:4px;border-radius:8px;border:2px solid #555;background:#000;color:#fff}
#val.has{border-color:#2e7d32}
.row{display:flex;gap:6px;margin-top:6px}
.row button{flex:1;font-size:18px;padding:12px 4px;border:0;border-radius:8px;color:#fff;font-weight:bold}
.prev{background:#444}.next{background:#1565c0;flex:2!important}.x{background:#b71c1c}.p{background:#6a1b9a}.save{background:#2e7d32}.orig{background:#555}.dl{background:#37474f}
</style></head><body>
<div id="top"><span id="num"></span><span id="type"></span><span id="cnt"></span><span id="st"></span></div>
<div id="view"><img id="img" alt=""></div>
<div id="panel">
 <input id="val" inputmode="numeric" pattern="[0-9]*" autocomplete="off" placeholder="الرقم بدون كسور">
 <div class="row"><button class="x" onclick="setv('X')">X</button><button class="p" onclick="setv('P')">P</button>
  <button class="orig" id="ob" onclick="toggle()">الأصلية</button><button class="save" onclick="save()">حفظ</button></div>
 <div class="row"><button class="prev" onclick="go(-1)">السابق</button><button class="next" onclick="go(1)">التالي ◀</button><button class="dl" onclick="dl()">JSON</button></div>
</div>
<script>
const T=location.pathname.split('/')[1];let items=[],lab={},i=0,orig=false,dirty=false;
const $=id=>document.getElementById(id);
async function init(){items=await (await fetch(`/${T}/items`)).json();lab=await (await fetch(`/${T}/labels`)).json();
 const f=items.findIndex(it=>!lab[it.n]);i=f<0?0:f;
 $('val').addEventListener('input',()=>{const v=$('val').value.toUpperCase().replace(/[^0-9XP]/g,'');$('val').value=v;keep(v);});
 $('val').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();go(1)}});
 const ph=()=>document.documentElement.style.setProperty('--ph',$('panel').offsetHeight+'px');ph();addEventListener('resize',ph);
 show();setInterval(()=>{if(dirty)save()},15000);}
function keep(v){const it=items[i];if(v)lab[it.n]={n:it.n,filename:it.filename,reading:v,type:it.type};else delete lab[it.n];dirty=true;upd()}
function upd(){$('cnt').textContent=Object.keys(lab).length+'/'+items.length;$('val').classList.toggle('has',!!$('val').value)}
function pre(k){if(items[k]){new Image().src=`/${T}/img/${items[k].n}.jpg`}}
function show(){const it=items[i];orig=false;$('ob').textContent='الأصلية';$('img').src=`/${T}/img/${it.n}.jpg`;$('view').scrollTop=0;
 $('num').textContent='#'+it.n;$('type').textContent=it.type;$('val').value=(lab[it.n]||{}).reading||'';upd();pre(i+1);pre(i+2)}
function toggle(){const it=items[i];orig=!orig;$('img').src=`/${T}/img/${it.n}${orig?'_o':''}.jpg`;$('ob').textContent=orig?'المكبّرة':'الأصلية'}
function setv(v){$('val').value=v;keep(v);go(1)}
function go(d){if(dirty)save();const j=i+d;if(j<0||j>=items.length){if(j>=items.length)$('st').textContent='آخر صورة ✔ اضغط حفظ';return}i=j;show()}
async function save(){try{const r=await fetch(`/${T}/save`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(lab)});
 const j=await r.json();dirty=false;$('st').textContent='✔ '+j.saved+' '+new Date().toLocaleTimeString().slice(0,5)}catch(e){$('st').textContent='✘ نزّل JSON'}}
function dl(){const b=new Blob([JSON.stringify({saved_at:new Date().toISOString(),labels:Object.values(lab)},null,1)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='owner_labels_b6.json';a.click()}
init();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "private, max-age=86400" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _parts(self):
        p = self.path.split("?")[0].strip("/").split("/")
        return p[1:] if p and p[0] == TOK else None

    def do_GET(self):
        p = self._parts()
        if p is None:
            return self._send(404, b"not found", "text/plain")
        if p in ([], [""]):
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if p == ["items"]:
            return self._send(200, json.dumps(ITEMS).encode(), "application/json")
        if p == ["labels"]:
            d = json.load(open(OUT)) if os.path.exists(OUT) else {"labels": []}
            return self._send(200, json.dumps({str(x["n"]): x for x in d["labels"]}).encode(), "application/json")
        if len(p) == 2 and p[0] == "img":
            f = f"{D}/img/{os.path.basename(p[1])}"
            if os.path.exists(f):
                return self._send(200, open(f, "rb").read(), "image/jpeg", cache=True)
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self._parts() != ["save"]:
            return self._send(404, b"not found", "text/plain")
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        ok = {}
        for v in d.values():
            r = str(v.get("reading", "")).strip().upper()
            n = int(v.get("n", 0))
            if r and (r.isdigit() or r in ("X", "P")) and 1 <= n <= len(ITEMS) and v.get("filename") == ITEMS[n - 1]["filename"]:
                it = ITEMS[n - 1]
                ok[n] = {"n": n, "filename": it["filename"], "reading": r, "type": it["type"]}
        out = {"saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "labels": [ok[k] for k in sorted(ok)]}
        old = json.load(open(OUT))["labels"] if os.path.exists(OUT) else []
        keep = {x["n"]: x for x in old}
        keep.update(ok)
        out["labels"] = [keep[k] for k in sorted(keep)]
        json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
        json.dump(out, open(f"{D}/owner_labels_{int(time.time())}.json", "w"))
        self._send(200, json.dumps({"saved": len(ok)}).encode(), "application/json")

    def log_message(self, fmt, *a):
        if " 404 " in (fmt % a): open(D + "/404.log", "a").write(self.path.split("/")[-1] + "\n")


ThreadingHTTPServer(("0.0.0.0", 8090), H).serve_forever()
