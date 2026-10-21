"""Ask strong LLMs (via the project's OpenAI-compatible proxy) to critique a brief. Saves raw answers under
docs/consult/. Usage: python3 lab/consult.py docs/consult/brief.md model1,model2 [tag]
Answers are advice, not truth: everything adopted must still be measured on our eval sets (contract §3)."""
import os, sys, time, yaml, pathlib
from openai import OpenAI
cfg = yaml.safe_load(open(os.path.expanduser("~/.genspark_llm.yaml")))["openai"]
client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
brief = open(sys.argv[1], encoding="utf-8").read()
models = sys.argv[2].split(","); tag = sys.argv[3] if len(sys.argv) > 3 else time.strftime("%Y-%m-%d")
SYS = ("You are a senior computer-vision engineer who has shipped on-device OCR/meter-reading systems in production. "
       "Be concrete, critical and quantitative. Prefer methods with evidence (papers, known deployments). "
       "Explicitly list what you would NOT do and why. Do not flatter. Answer in English, structured by question number.")
for m in models:
    t0 = time.time()
    try:
        r = client.chat.completions.create(model=m, messages=[{"role": "system", "content": SYS}, {"role": "user", "content": brief}])
        txt = r.choices[0].message.content
    except Exception as ex:  # noqa: BLE001
        txt = f"ERROR: {ex}"
    out = pathlib.Path(sys.argv[1]).parent / f"answer-{tag}-{m.replace('/', '_')}.md"
    out.write_text(f"# {m} — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} ({time.time() - t0:.0f}s)\n\n{txt}\n", encoding="utf-8")
    print(m, len(txt), "chars", f"{time.time() - t0:.0f}s", flush=True)
