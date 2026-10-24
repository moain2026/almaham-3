"""Ask several strong LLMs the same brief (docs/consult/brief-*.md) and store raw answers for the record.
Usage: python3 consult.py <brief.md> <out_dir> [models,comma]
Uses ~/.genspark_llm.yaml (Genspark proxy). Nothing from the private data is sent — only the brief text.
2026-10-24: the proxy cuts non-streaming responses at 120 s (Cloudflare 524; hit twice before). Fix: stream=True
(keeps the connection alive) + EFFORT default medium + up to 2 retries. Available models probed 2026-10-24:
gpt-5.2, gpt-5.1, claude-opus-4-5, claude-sonnet-4-5. Full list via GET /v1/models (76 models, 2026-10-24) — strongest:
claude-opus-5-5, claude-fable-5-1, gpt-6-astra, gpt-5.5 (owner: always use the strongest, never the default ones)."""
import os, sys, time, yaml
from pathlib import Path
from openai import OpenAI
cfg = yaml.safe_load(open(Path.home() / ".genspark_llm.yaml"))["openai"]
client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=900, max_retries=0)
brief = open(sys.argv[1], encoding="utf-8").read(); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
models = (sys.argv[3] if len(sys.argv) > 3 else "claude-opus-5-5,claude-fable-5-1,gpt-6-astra,gpt-5.5").split(",")
SYS = ("You are a senior computer-vision researcher and production ML engineer (OCR, tiny detectors on mobile, "
       "selective prediction). Be rigorous, critical, concrete and cite papers by name/year. No flattery.")
def ask(m):
    kw = {"model": m, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": brief}], "stream": True}
    if m.startswith("gpt-5"):
        kw["reasoning_effort"] = os.environ.get("EFFORT", "medium")
    parts = []
    for ch in client.chat.completions.create(**kw):
        d = ch.choices[0].delta.content if ch.choices else None
        if d:
            parts.append(d)
    return "".join(parts)
for m in models:
    t0 = time.time(); txt = ""
    for attempt in range(3):
        try:
            txt = ask(m); break
        except Exception as ex:  # noqa: BLE001
            txt = f"ERROR (attempt {attempt + 1}): {ex}"; print(m, "retry", attempt + 1, str(ex)[:80], flush=True); time.sleep(20)
    (out / f"{m}.md").write_text(f"# {m} — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} ({time.time()-t0:.0f}s)\n\n{txt}\n", encoding="utf-8")
    print(m, len(txt), f"{time.time()-t0:.0f}s", flush=True)
