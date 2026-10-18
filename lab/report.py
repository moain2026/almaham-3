"""Generate benchmark_report.md tables from the e2e JSON results. Usage: python3 report.py <tag> > ../docs/benchmark_report_tables.md"""
import json
import sys

import paths


def table(tag):
    out = []
    for mode in ("A", "B"):
        d = json.load(open(paths.RESULTS_ENGINES / f"digitnet_{tag}_{mode}.json"))
        s = d["summary"]
        out.append(f"### الوضع {mode} ({'مستطيل العداد' if mode == 'A' else 'الصورة كاملة'}) — `{d['models']}`\n")
        out.append("| المقياس | القيمة |\n|---|---|")
        out.append(f"| مطابقة الرقم كامل (المقروءة) | **{s['exact']}/{s['n_readable']}** ({100 * s['exact'] / s['n_readable']:.1f}%) |")
        out.append(f"| مطابقة على الواضحة فقط | {s['exact_clear']}/{s['n_clear']} ({100 * s['exact_clear'] / s['n_clear']:.1f}%) |")
        out.append(f"| دقة الخانة (محاذاة يمين) | {100 * s['digit_acc']:.1f}% |")
        out.append(f"| ما انقرأ (فاضي) | {s['empty']}/{s['n_readable']} |")
        out.append(f"| غلط (أي ثقة) | {s['wrong']}/{s['n_readable']} |")
        out.append(f"| **غلط وواثق** | **{s['wrong_confident']}/{s['n_readable']}** ({100 * s['wrong_confident'] / s['n_readable']:.1f}%) |")
        out.append(f"| دقة القراءات الواثقة | {s['confident_correct']}/{s['confident_total']} |")
        out.append(f"| الصور غير المقروءة المرفوضة (فاضي) | {s['unreadable_rejected']}/{s['unreadable_n']} |")
        out.append(f"| الزمن الكلي p50 / p95 / max | {s['p50_ms']} / {s['p95_ms']} / {s['max_ms']} ms ({s['hardware']}) |")
        out.append(f"| مراحل p50: تجهيز المحدِّد / المحدِّد / تجهيز السطر / القارئ / التجميع | {s['stage_loc_prep_p50_ms']} / {s['stage_locate_p50_ms']} / {s['stage_line_prep_p50_ms']} / {s['stage_read_p50_ms']} / {s['stage_assemble_p50_ms']} ms |")
        out.append("")
        fails = [r for r in d["rows"] if r["truth"] and not r["ok"]]
        out.append(f"#### الصور الفاشلة في الوضع {mode} ({len(fails)})\n")
        out.append("| الصورة | النوع | الصعوبة | الصحيح | طلع | الخام | الحالة | واثق؟ | السطر وُجد؟ |\n|---|---|---|---|---|---|---|---|---|")
        for r in fails:
            out.append(f"| {r['file']} | {r['type']} | {r['difficulty']} | {r['truth']} | {r['value'] or '—'} | `{r['raw'] or '—'}` | {r['status']} | {'نعم' if r['confident'] else 'لا'} | {'نعم' if r['line_found'] else 'لا'} ({r['line_score']}) |")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    print(table(sys.argv[1]))
