import json,glob,re,os,statistics as st
def parse(tag):
    s=open(f'lab/logs/eval_{tag}.log').read()
    A=json.loads(re.search(r'^A (\{.*\})',s,re.M).group(1)); B=json.loads(re.search(r'^B (\{.*\})',s,re.M).group(1))
    th=json.loads([l for l in s.splitlines() if '"by_type"' in l][-1])
    rc=json.load(open(f'benchmark/results/engines/risk_coverage_{tag}.json'))['gates']
    g=rc['OK & min_conf>=0.55 & alt<0.5']['all']; g45=rc['OK & min_conf>=0.45']['all']
    return dict(tag=tag,A=A['exact'],B=B['exact'],T=th['exact'],bt=th['by_type'],acc=g['accepted'],wr=g['wrong'],acc45=g45['accepted'],wr45=g45['wrong'])
loc=sorted(os.path.basename(f)[5:-4] for f in glob.glob('lab/logs/eval_auto_loc_s*.log'))
rd=sorted(os.path.basename(f)[5:-4] for f in glob.glob('lab/logs/eval_auto_rd_s*.log'))
L=[parse(t) for t in loc]; R=[parse(t) for t in rd]
def tbl(rows):
    out=["| الوسم | 49-A | 49-B | 34 | CRYSTAL | EMETER | OTHER | ≥0.55&alt مقبول/خاطئ | ≥0.45 مقبول/خاطئ |","|---|---|---|---|---|---|---|---|---|"]
    for r in rows: out.append(f"| {r['tag']} | {r['A']} | {r['B']} | {r['T']} | {r['bt']['CRYSTAL']} | {r['bt']['EMETER_GREEN']} | {r['bt']['OTHER']} | {r['acc']}/{r['wr']} | {r['acc45']}/{r['wr45']} |")
    return "\n".join(out)
def summ(rows):
    o=[]
    for k,lab in (('A','49-A'),('B','49-B'),('T','34')):
        v=[r[k] for r in rows]; o.append(f"- **{lab}**: متوسط {st.mean(v):.2f}، انحراف {st.pstdev(v):.2f}، مدى {min(v)}–{max(v)}، وسيط {st.median(v)}")
    acc=[r['acc'] for r in rows]; wr=[r['wr'] for r in rows]
    o.append(f"- **بوابة OK & min_conf≥0.55 & alt<0.5**: مقبول متوسط {st.mean(acc):.1f} ({min(acc)}–{max(acc)})، خاطئ متوسط {st.mean(wr):.2f} ({min(wr)}–{max(wr)})؛ تشغيلات بصفر خطأ: {sum(1 for w in wr if w==0)}/{len(wr)}")
    acc=[r['acc45'] for r in rows]; wr=[r['wr45'] for r in rows]
    o.append(f"- **بوابة OK & min_conf≥0.45**: مقبول متوسط {st.mean(acc):.1f} ({min(acc)}–{max(acc)})، خاطئ متوسط {st.mean(wr):.2f} ({min(wr)}–{max(wr)})")
    return "\n".join(o)
base=parse('m1loc_ft6m2_s1')
Lt=[r['T'] for r in L]; Lb=[r['B'] for r in L]; La=[r['A'] for r in L]
Rt=[r['T'] for r in R]
doc=f"""# تحليل 58 دورة autotrain (Contabo، 2026-10-21 → 2026-10-24) — وكيل S الخليفة، 2026-10-24 06:40 مكة

**ما حدث:** حلقتا systemd على Contabo عملتا 3 أيام بلا انقطاع وأنتجتا {len(L)} محدِّداً و{len(R)} قارئاً (بذور 102–134، نفس الوصفة، تختلف البذرة فقط). لكن **الدفع إلى `auto-training` فشل في كل دورة** (`fatal: could not read Username for 'https://github.com'`) لأن خدمة systemd لا تملك `HOME` فلا تجد `~/.git-credentials`. أصلحته (`Environment=HOME=/root` في الخدمتين + `git config --system credential.helper store --file=/root/.git-credentials`) ودفعتُ الـ64 commit إلى `auto-training` ثم دمجتها في `genspark_ai_developer`، والأرشيف (أوزان وسيطة/سجلات/صور مراجعة) إلى الخاص (`92ce3a2`). صفحة النتائج للمالك كانت تعرض ما وصل من sandbox فقط (تشغيلان).

**لماذا هذا مهم:** أول **توزيع بذور** حقيقي (n={len(L)} وn={len(R)}) لنفس الوصفة. كل ادعاءات «+1/+2» السابقة كانت ببذرة واحدة. الآن نعرف ضوضاء البذرة بالقياس.

## 1) المحدِّد: `locator_m1_augv2` → m3 loc (463/68، موزون) + scene_s1، 3000 خطوة، AUG v2؛ القارئ الثابت = `reader_ft6m2_s1` (n={len(L)})
{summ(L)}

المرجع المنشور (locator_m1_augv2 + reader_ft6m2_s1): A {base['A']}، B {base['B']}، 34: {base['T']}، بوابة ≥0.55&alt {base['acc']} مقبولة / {base['wr']} خاطئة.

**القراءة:** إعادة تدريب المحدِّد على m3 ترفع الاختبار البشري 34 من 21 إلى **{st.mean(Lt):.1f} ± {st.pstdev(Lt):.1f}** ({sum(1 for t in Lt if t>=21)}/{len(Lt)} بذرة ≥ 21، أي لا بذرة أسوأ من المرجع) وB من 19 إلى {st.mean(Lb):.1f} ± {st.pstdev(Lb):.1f}؛ A ثابت ({st.mean(La):.1f} ± {st.pstdev(La):.1f} حول 22 — المستطيل اليدوي لا يستفيد من محدِّد العداد الكامل). **لكن** البوابة الصارمة تسوء: متوسط {st.mean([r['wr'] for r in L]):.2f} خطأ مقبول (المرجع 0) و{sum(1 for r in L if r['wr']==0)}/{len(L)} فقط بصفر خطأ. المحدِّد الأفضل يُدخل صوراً أكثر إلى حيز «واثق» ومنها خاطئة — البوابة الحالية (ثقة الخانة فقط) **لا ترى خطأ التوطين**.

## 2) القارئ: `reader_ft6m2_s1` → ft6m3 (856/173) + line_s1 + line_crystal_opt2، 3000 خطوة، AUG v2؛ المحدِّد الثابت = `locator_m1_augv2` (n={len(R)})
{summ(R)}

**القراءة:** لا تحسّن. 34: {st.mean(Rt):.1f} ± {st.pstdev(Rt):.1f} (المرجع 21)؛ **Crystal 2/7 في {sum(1 for r in R if r['bt']['CRYSTAL']=='2/7')}/{len(R)} بذرة**؛ EMETER {st.mean([int(r['bt']['EMETER_GREEN'][0]) for r in R]):.1f}/6 (المرجع 2/6). الاصطناعي Crystal (line_crystal_opt2، 3000 عيّنة من patch optical2) **لم يحرّك Crystal في أي بذرة** — هذا يغلق السؤال 2 من خطة التسليم بقياس قاطع. المكسب الوحيد: البوابة الصارمة أنظف قليلاً ({st.mean([r['wr'] for r in R]):.2f} خطأ متوسط، {sum(1 for r in R if r['wr']==0)}/{len(R)} بصفر) لأن القارئ أكثر تحفّظاً، لا أدق.

## 3) تشغيلات S السابق المستأنفة (قُيّمت اليوم في sandbox، المحدِّد m1)
| القارئ | 49 A/B | 34 | Crystal | EMETER | بوابة ≥0.55&alt مقبول/خاطئ |
|---|---|---|---|---|---|
| reader_ft6m2_cry_s1 (ft6m2 + Crystal اصطناعي، نفس بذرة ft6m2_s1) | 22/20 | 21 | 2/7 | 1/6 | 21/1 |
| reader_ft6m3_cry_s1 | 20/20 | 19 | 2/7 | 1/6 | 20/2 |
| reader_ft6m3_s0 | 21/18 | 20 | 2/7 | 2/6 | 17/0 |
| reader_ft6m3_s1 | 20/19 | 20 | 2/7 | 2/6 | 15/0 |

المقارنة المضبوطة (ft6m2_s1 مقابل ft6m2_cry_s1، نفس البذرة والبيانات الحقيقية، الفرق = الاصطناعي Crystal فقط): 22/19/21 → 22/20/21، Crystal 2/7 → 2/7، القصيرة لم تتحرك. **لا أثر.**

## 4) القرارات
1. **Crystal الاصطناعي v2 مُغلق بقياس** ({len(R)+4} تشغيلاً، 0 تحرّك). السبب الجذري (`crystal-root-cause-2026-10-21.md`) قائم: المشكلة **تمثيلية** (حدّ الكسر/النقطة ≤1 بكسل) لا نقص اصطناعي. الرافعة التالية للقارئ = تغيير التمثيل (رأس «آخر خانة صحيحة» — الخيار A في المستند) أو بيانات حقيقية Crystal/SMART_YELLOW جديدة من D، لا بذور إضافية.
2. **حلقة القارئ التلقائية توقّفت** (كانت تهدر نواة على وصفة ثبت عقمها). حلقة المحدِّد تستمر لأنها الوحيدة التي تعطي مكسباً مقاساً.
3. **لا أختار «أفضل بذرة» على الـ49/34**: الأعلى (auto_loc_s124: A25/B23/34:24) هو ذيل التوزيع على الميزان نفسه ⇒ اختياره = ضبط على مجموعة الاختبار (قاعدة المالك). val المحجوز (66/68 في **كل** البذور) غير مميِّز. البديل الصادق: **متوسط أوزان** (weight averaging/SWA) لعدة بذور ⇒ نموذج واحد يُقيَّم مرة واحدة. يُقاس تالياً.
4. **البوابة تحتاج إشارة توطين**: مع محدِّد m3 يرتفع الخطأ المقبول من 0 إلى 1–4/73. قبل اعتمادها في `assemble.py`/`ReadingAssembler.kt` تُضاف ثقة المحدِّد (ذروة السطر) ± اتفاق TTA وتُقاس على الـ73 من جديد.

## 5) الأثر على خطة التسليم §4
- الخطوة 1 (مراجعة auto-training + دمج): ✔ تمّت. الخطوة 2 (Crystal الاصطناعي): ✔ مغلقة سلبياً. الخطوة 3 (محدِّد m3): ✔ مقاس — مكسب حقيقي على 34 (+2) وB (+1)، لا على A، ويكسر البوابة.
- الخطوة 4 (الرفض) تتقدّم إلى الأولوية الأولى مع إضافة إشارة التوطين؛ ثم weight averaging للمحدِّد؛ ثم الشحن.

كل رقم أعلاه من `benchmark/results/engines/{{digitnet_<tag>_A,B; testset_human_<tag>; risk_coverage_<tag>}}.json` و`lab/logs/eval_<tag>.log`.

## ملحق أ — المحدِّدات (n={len(L)})
{tbl(L)}

## ملحق ب — القرّاء (n={len(R)})
{tbl(R)}
"""
open('docs/research/autotrain-seed-analysis-2026-10-24.md','w').write(doc)
print("ok", len(doc))
