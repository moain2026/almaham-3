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
import eval_e2e as e2e
from gate_v2_study import tta_views  # noqa: E402

MODELS = {}      # name -> Engine
LOCK = threading.Lock()   # ORT sessions are per-engine; keep one request at a time (4 vCPU box, also runs training)
STORE = Path(os.environ.get("WEBDEMO_STORE", HERE.parent.parent / "data" / "webdemo"))
MAX_UPLOAD = 12 * 1024 * 1024

# ---- owner labelling page for the 49 evaluation photos (label.html) ----
# Photos come from lab/paths.photo (private data dir); labels are written to LABEL_CSV (private store), never to
# benchmark/data/ground_truth.csv automatically — a human diff + commit does that (contract §3: eval set is sacred).
import paths  # noqa: E402
LABEL_CSV = Path(os.environ.get("WEBDEMO_LABELS", "")) if os.environ.get("WEBDEMO_LABELS") else None
LABEL_TOKEN = os.environ.get("WEBDEMO_LABEL_TOKEN", "")   # optional ?t=... gate for the label page
_IMG_CACHE = {}


def _label_items():
    import csv
    gt = list(csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")))
    return [{"idx": i, "filename": g["filename"], "hint": f'{g["meter_type"]} · {g["difficulty"]}'} for i, g in enumerate(gt)]


def _load_labels():
    import csv
    p = LABEL_CSV or (STORE / "labels_owner_49.csv")
    if not p.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(p, encoding="utf-8")):
        out[r["filename"]] = {"reading": r["reading"], "flag": r["flag"]}  # last write wins (append-only log)
    return out


def _save_label(filename, reading, flag):
    import csv
    p = LABEL_CSV or (STORE / "labels_owner_49.csv")
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["filename", "reading", "flag", "ts"])
        w.writerow([filename, reading, flag, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())])


def _photo_bytes(fn, w=None, zoom=False):
    key = (fn, w, zoom)
    if key in _IMG_CACHE:
        return _IMG_CACHE[key]
    if not fn.replace(".", "").replace("_", "").isalnum():
        return None
    im = cv2.imread(paths.photo(fn), cv2.IMREAD_COLOR)
    if im is None:
        return None
    if zoom:
        # upper 72% (where the screen is in the upright photos), upscaled + CLAHE — same as erp_label.enhanced_view
        H, W = im.shape[:2]
        crop = im[: int(H * 0.72)]
        s = 1100 / crop.shape[1]
        crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        lab[..., 0] = cv2.createCLAHE(3.0, (8, 8)).apply(lab[..., 0])
        im = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    elif w:
        s = w / im.shape[1]
        im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    b = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes()
    _IMG_CACHE[key] = b
    return b


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
        # Gate v2 (docs/research/gate-v2-2026-10-24.md, measured on val-m4 e2e: 130/11 -> 106/2 wrong with TTA agreement):
        # G0 = OK & every digit score>=0.45 & alt<0.5*score (no 7-segment veto) ; TTA = same string under gamma 0.7/1.4,
        # scale 0.92/1.08. Only a gated reading fills the field; otherwise the field stays EMPTY and the guess is shown small.
        g0 = r.status == "OK" and r.value != "" and all(d.score >= 0.45 and d.alt_score < 0.5 * d.score for d in r.digits)
        tta = [engine.read(v)[0].value for v in tta_views(crop)] if g0 else []
        gated = g0 and all(t == r.value for t in tta)
    total = (time.perf_counter() - t0) * 1e3
    ok, png = cv2.imencode(".png", ri)
    return {"reading": r.value if gated else "", "guess": r.value, "gated": bool(gated), "g0": bool(g0), "tta": tta,
            "min_conf": round(float(r.min_conf), 3), "status": r.status, "raw": r.text, "line_found": line_rect is not None,
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
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path); q = parse_qs(u.query); route = u.path.rstrip("/").split("/")[-1]
        if route == "label":
            if LABEL_TOKEN and q.get("t", [""])[0] != LABEL_TOKEN:
                return self._send(403, {"error": "token"})
            return self._send(200, (HERE / "label.html").read_bytes(), "text/html; charset=utf-8")
        if route == "label_data":
            return self._send(200, {"items": _label_items(), "labels": _load_labels()})
        if "/results" in u.path:   # public static results snapshot (lab/autotrain/publish_results.sh); no customer photos inside
            rd = Path(os.environ.get("RESULTS_DIR", "/opt/almaham/results_public"))
            fn = Path(u.path.split("/results", 1)[1].strip("/") or "index.html").name
            f = rd / fn
            if not f.is_file():
                return self._send(404, {"error": "not found"})
            ct = "text/html; charset=utf-8" if fn.endswith(".html") else "application/zip" if fn.endswith(".zip") else "text/plain; charset=utf-8"
            self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(f.stat().st_size))
            self.send_header("Cache-Control", "no-store"); self.end_headers()
            with open(f, "rb") as fh:
                import shutil; shutil.copyfileobj(fh, self.wfile)
            return
        if route == "dl":  # one-off private downloads (e.g. ZBook bootstrap); token + fixed dir, basename only
            dl_dir = os.environ.get("DL_DIR"); tok = os.environ.get("DL_TOKEN")
            fn = Path(q.get("f", [""])[0]).name
            if not (dl_dir and tok and fn) or q.get("t", [""])[0] != tok or not (Path(dl_dir) / fn).is_file():
                return self._send(404, {"error": "not found"})
            return self._send(200, (Path(dl_dir) / fn).read_bytes(), "text/plain; charset=utf-8")
        if route == "photo":
            b = _photo_bytes(q.get("f", [""])[0], int(q.get("w", [0])[0]) or None, q.get("zoom", ["0"])[0] == "1")
            if b is None:
                return self._send(404, {"error": "no photo"})
            self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "private, max-age=86400"); self.end_headers(); return self.wfile.write(b)
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
                meta["feedback"] = {"correct": bool(fb.get("correct")), "truth": str(fb.get("truth", ""))[:12], "skip": bool(fb.get("skip")),
                                    "note": str(fb.get("note", ""))[:300], "ts": time.time(),
                                    "meter_type": (str(fb.get("meter_type") or "")[:20] or None),
                                    "screen_rect": fb.get("screen_rect") if isinstance(fb.get("screen_rect"), list) and len(fb.get("screen_rect")) == 4 else None}
                p.write_text(json.dumps(meta, ensure_ascii=False))
                return self._send(200, {"ok": True})
            except Exception as ex:  # noqa: BLE001
                return self._send(400, {"error": str(ex)})
        if self.path.rstrip("/").endswith("/label_save"):
            try:
                d = json.loads(body)
                fn = str(d["filename"]); flag = str(d.get("flag", ""))[:1].upper()
                reading = "".join(ch for ch in str(d.get("reading", "")) if ch.isdigit())[:9]
                assert fn in {it["filename"] for it in _label_items()}, "unknown file"
                assert flag in ("", "X", "B"), "bad flag"
                assert flag or reading, "empty"
                _save_label(fn, reading, flag)
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
