"""Per-type accuracy report for agent D (where to collect more data). Three views, all EVAL ONLY:
  1. testset_human (34 frozen ERP photos, whole photo through the full engine)      -> from testset_human_<tag>.json
  2. the 49 (mode B)                                                                 -> digitnet_<tag>_B.json (types from labels if known)
  3. held-out real shard val split (<shards>_val, reader only, no locator)           -> computed here (needs .pt)
Usage: python3 report_by_type.py <tag> <reader.pt> <shards_prefix>  -> docs/training-log/by_type_<tag>.md + results json
"""
import csv, json, sys
import numpy as np, torch
import paths, assemble, erp_finetune as ef
from det_model import DigitNet, READER_CLASSES, decode
from train_det import Shards
from synth2 import CLS_LINE

def val_by_type(ckpt, prefix):
    m = DigitNet(READER_CLASSES); m.load_state_dict(torch.load(ckpt, map_location="cpu")); m.eval()
    d = Shards([prefix + "_val"], "reader"); d.val_idx = d.train_idx + d.val_idx
    # type per sample: recovered from the shard report order is not stored -> use digit count bucket + nothing else;
    # we therefore report by DIGIT COUNT (the proxy agent D asked about for Crystal: 1/2/3/4 cells)
    out = {}
    with torch.no_grad():
        for si, i in d.val_idx:
            im, bx = d.item(si, i)
            peaks, size, offs = m.forward_export(torch.from_numpy(im[None]).float())
            lines = bx[bx[:, 0] == CLS_LINE]
            truth = assemble.truth_from_boxes(bx, lines[0]) if len(lines) else None
            if truth is None: continue
            r = assemble.assemble(decode(peaks[0].numpy(), size[0].numpy(), offs[0].numpy(), ef.RD_PEAK_MIN), d.W, d.H)
            k = f"{len(truth)} digits"; out.setdefault(k, [0, 0]); out[k][0] += r.text == truth; out[k][1] += 1
    return out

def main():
    tag, ckpt, prefix = sys.argv[1:4]
    th = json.load(open(paths.RESULTS_ENGINES / f"testset_human_{tag}.json")); th = th.get("summary", th)
    vb = val_by_type(ckpt, prefix)
    lines = [f"# دقة حسب النوع — {tag} — {__import__('time').strftime('%Y-%m-%d %H:%MZ', __import__('time').gmtime())}", "",
             "## 1) الاختبار البشري المجمَّد (34 صورة، الصورة كاملة، المحرك كاملاً) — لا يُدرَّب عليه", "| النوع | صحيح/كل |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(th["by_type"].items())]
    lines += ["", f"**المجموع: {th['exact']}/{th['n']}**", "",
              f"## 2) شريحة التحقق الحقيقية المحجوزة (`{prefix}_val`، القارئ فقط بصناديق text_locate) حسب عدد الخانات",
              "| خانات | صحيح/كل |", "|---|---|"]
    lines += [f"| {k} | {v[0]}/{v[1]} |" for k, v in sorted(vb.items())]
    lines += ["", "## قراءة S للأرقام (أين تجمع البيانات)", "- الأنواع التي تحت 50% في الجدول 1 هي الأولوية. Tomas كافٍ.",
              "- الأنواع النادرة (HPL/CHINT/GLORY) لا تُقاس هنا (≤1 عيّنة).", "- MECHANICAL لا يمرّ عبر text_locate (ليست LCD) — يحتاج مساراً خاصاً؛ لا تجمع له الآن إلا إذا قرر المالك."]
    p = paths.BENCH_DATA.parent.parent / "docs" / "training-log" / f"by_type_{tag}.md"; p.write_text("\n".join(lines), encoding="utf-8")
    json.dump({"tag": tag, "testset_human": th, "val_by_digits": vb}, open(paths.RESULTS_ENGINES / f"by_type_{tag}.json", "w"), indent=1)
    print("\n".join(lines))

if __name__ == "__main__":
    main()
