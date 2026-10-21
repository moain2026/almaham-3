"""Field web demo: phone camera -> same engine as the APK -> integer reading. Standard library only (no Flask).

  python3 server.py <models_dir> [port=8700] [store_dir=../../data/webdemo]

Routes
  GET  /            the page (camera + guide frame + optional finger rectangle)
  POST /read        multipart/form-data: photo=<jpeg>, rect=x1,y1,x2,y2 (normalized, optional), shipped=0|1
                    -> JSON {reading, status, raw, line_found, ms, crop_png_b64, id}
  POST /feedback    JSON {id, correct: true|false, truth: "1234"}   (stored next to the photo, private data only)
  GET  /health

Every photo + result + feedback is stored under store_dir (NOT in the public repo; pushed to the private repo
with scripts/private_data.sh push-dir). The engine is lab/eval_e2e.Engine — the Python mirror of MeterReader.kt.
"""
import base64, json, os, sys, time, uuid, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import eval_e2e as e2e  # noqa: E402

MODELS = {}      # name -> Engine
LOCK = threading.Lock()   # ORT sessions are per-engine; keep one request at a time (4 vCPU box, also runs training)
STORE = Path(os.environ.get("WEBDEMO_STORE", HERE.parent.parent / "data" / "webdemo"))
MAX_UPLOAD = 12 * 1024 * 1024


def load_engines(spec):
    """spec: 'name=dir,name=dir' or a single dir (name 'default')."""
    for part in spec.split(","):
        name, _, d = part.partition("=")
        if not d:
            name, d = "default", name
        MODELS[name] = e2e.Engine(d)
        print("engine", name, d, flush=True)


def parse_multipart(body, ctype):
    boundary = ctype.split("boundary=")[1].encode()
    fields = {}
    for part in body.split(b"--" + boundary)[1:]:
        if part.strip() in (b"", b"--"):
            continue
        head, _, data = part.partition(b"\r\n\r\n")
        data = data.rstrip(b"\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        fields[name] = data
    return fields


def read_photo(jpeg_bytes, rect, engine):
    im = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        return None, "BAD_IMAGE"
    H, W = im.shape[:2]
    if rect:
        x1, y1, x2, y2 = [float(v) for v in rect.split(",")]
        x1, x2 = sorted((max(0, x1), min(1, x2))); y1, y2 = sorted((max(0, y1), min(1, y2)))
        crop = im[int(y1 * H):max(int(y1 * H) + 8, int(y2 * H)), int(x1 * W):max(int(x1 * W) + 8, int(x2 * W))]
    else:
        crop = im
    t0 = time.perf_counter()
    with LOCK:
        r, line_rect, lscore, ms, ri = engine.read(crop)
    total = (time.perf_counter() - t0) * 1e3
    ok, png = cv2.imencode(".png", ri)
    return {"reading": r.value, "status": r.status, "raw": r.text, "line_found": line_rect is not None,
            "line_score": round(float(lscore or 0), 3), "ms": round(total, 1),
            "crop_png_b64": base64.b64encode(png.tobytes()).decode(), "img_w": W, "img_h": H}, None


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

    def log_message(self, fmt, *a):  # quieter log, no client IPs in the public log
        sys.stdout.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % a)); sys.stdout.flush()

    def do_GET(self):
        if self.path.rstrip("/").endswith("/health") or self.path.startswith("/health"):
            return self._send(200, {"ok": True, "engines": list(MODELS), "stored": len(list(STORE.glob("*.jpg")))})
        if self.path == "/" or self.path.startswith("/?"):
            return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX_UPLOAD:
            return self._send(413, {"error": "too large"})
        body = self.rfile.read(n)
        if self.path.rstrip("/").endswith("/read"):
            f = parse_multipart(body, self.headers.get("Content-Type", ""))
            eng = MODELS.get(f.get("model", b"default").decode(), next(iter(MODELS.values())))
            rect = f.get("rect", b"").decode() or None
            res, err = read_photo(f.get("photo", b""), rect, eng)
            if err:
                return self._send(400, {"error": err})
            rid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
            STORE.mkdir(parents=True, exist_ok=True)
            (STORE / f"{rid}.jpg").write_bytes(f["photo"])
            meta = {k: v for k, v in res.items() if k != "crop_png_b64"}
            meta.update({"id": rid, "rect": rect, "model": [k for k, v in MODELS.items() if v is eng][0], "ts": time.time()})
            (STORE / f"{rid}.json").write_text(json.dumps(meta, ensure_ascii=False))
            res["id"] = rid
            return self._send(200, res)
        if self.path.rstrip("/").endswith("/feedback"):
            try:
                fb = json.loads(body)
                rid = str(fb["id"]); assert rid.replace("-", "").isalnum()
                p = STORE / f"{rid}.json"; meta = json.loads(p.read_text())
                meta["feedback"] = {"correct": bool(fb.get("correct")), "truth": str(fb.get("truth", ""))[:12], "ts": time.time()}
                p.write_text(json.dumps(meta, ensure_ascii=False))
                return self._send(200, {"ok": True})
            except Exception as ex:  # noqa: BLE001
                return self._send(400, {"error": str(ex)})
        return self._send(404, {"error": "not found"})


if __name__ == "__main__":
    load_engines(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8700
    if len(sys.argv) > 3:
        STORE = Path(sys.argv[3])
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    print(f"webdemo on 0.0.0.0:{port} store={STORE}", flush=True)
    srv.serve_forever()
