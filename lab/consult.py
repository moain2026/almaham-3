"""Ask several strong LLMs the same brief (docs/consultations/brief-*.md) and store raw answers for the record.
Usage: python3 consult.py <brief.md> <out_dir> [models,comma]
Uses OPENAI_API_KEY/OPENAI_BASE_URL (Genspark proxy). Nothing from the private data is sent — only the brief text."""
import os, sys, json, time, yaml
from pathlib import Path
from openai import OpenAI
cfg = yaml.safe_load(open(Path.home() / ".genspark_llm.yaml"))["openai"]
client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
brief = open(sys.argv[1], encoding="utf-8").read(); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
models = (sys.argv[3] if len(sys.argv) > 3 else "gpt-5.2,gpt-5.1,gpt-5").split(",")
SYS = ("You are a senior computer-vision researcher and production ML engineer (OCR, tiny detectors on mobile, "
       "selective prediction). Be rigorous, critical, concrete and cite papers by name/year. No flattery.")
for m in models:
    t0 = time.time()
    try:
        kw = {"model": m, "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": brief}]}
        if m.startswith("gpt-5"):
            kw["reasoning_effort"] = os.environ.get("EFFORT", "medium")
        r = client.chat.completions.create(**kw)
        txt = r.choices[0].message.content
    except Exception as ex:  # noqa: BLE001
        txt = f"ERROR: {ex}"
    (out / f"{m}.md").write_text(f"# {m} — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} ({time.time()-t0:.0f}s)\n\n{txt}\n", encoding="utf-8")
    print(m, len(txt), f"{time.time()-t0:.0f}s", flush=True)
