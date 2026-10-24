## [Unreleased] — 2026-10-20 جلسة الوكيل S (الخليفة)

## 2026-10-24 ج (وكيل S، 13:00–14:30 مكة)
- lab: `eval_valm4_e2e.py` (e2e على val-m4 مع clean65/seen112 + McNemar)، `gate_v2_study.py` (G0/TTA/prev-window مكوّنًا مكوّنًا).
- research: `docs/research/gate-v2-2026-10-24.md` — clean65 e2e 49 vs 47، TTA يُسقط 9/11 خطأ، نافذة prev تقتل أخطاء الطول، المحقق السباعي يُفرغ `confident`، LINE_CLIP مغلق.
- results: `valm4_e2e_{ref_m1loc_ft6m2_s1,loc_m4_s0_rd_m4_s0}.json`، `gate_v2_*.json`، `valm4_reader_w1.0_scratch_s0.json`.
- train: `locator_m4_s0_full` (3000)، `reader_m4_w1.0_scratch_s0_c6k` (استكمال 6000) أُطلقا في السندبوكس.

## 2026-10-24 ب (وكيل S، 05:45–09:30 مكة)
- data: owner field uploads (97) mirrored to private `webdemo/field/` + cron `lab/autotrain/mirror_field.sh` (5 min).
- fix(autotrain): `export HOME` inside `auto_push.sh`/`train_loop.sh`; PUSH_FAILED alarm on results page; Contabo push verified.
- consult: `lab/consult.py` streaming + strongest models by default; brief + 6 answers + `decision-2026-10-24.md`.
- research: `environment-and-plan-2026-10-24.md`, `crystal-dot-audit-2026-10-24.md` (+5 figures), `autotrain-seed-analysis-2026-10-24.md` (soups).
- lab: `text_locate.py` v2 `--meter-box --only-unlocated`; `build_meter_shards.py` writes `<out>_keys.json`.
- data: `benchmark/data/erp/poisoned_m3_short_2026-10-24.json` (9 poisoned m3 samples, to exclude in m4).

## 2026-10-24 (وكيل S الخليفة)
- fix(lab): `eval_vote.py` يتخطى الصور المقروءة بلا صندوق سطر مرجعي (23072) — كان يُسقط `eval_ckpt.sh` منذ GT v3.
- fix(autotrain/Contabo): `HOME=/root` في خدمتي systemd + credential helper على مستوى النظام؛ استرداد 64 دورة غير مدفوعة (10-21→10-24) إلى `auto-training` ودمجها هنا؛ أرشيف الخاص `92ce3a2`.
- eval: 4 قرّاء مستأنفون من S السابق (ft6m2_cry_s1، ft6m3_cry_s1، ft6m3_s0/s1) — صفوف في runs.md.
- docs: `docs/research/autotrain-seed-analysis-2026-10-24.md` (n=27 محدِّد، n=31 قارئ).
- ops: `almaham-autotrain-reader` متوقفة/معطّلة على Contabo (الوصفة عقيمة بقياس 35 تشغيلاً).

- feat: `lab/webdemo/` تجربة ميدانية عبر المتصفح على https://basirapp.site/meter/ (كاميرا الهاتف → نفس المحرك → قراءة صحيحة فقط؛ حفظ الصور والتصحيحات بشكل خاص؛ `deploy_contabo.sh`، `caddy_snippet.txt`).
- research: `docs/research/screen-autofind-2026-10-21.md` — قصّ تلقائي للشاشة (CamScanner-style) مقاس على الـ49: `lab/screen_quad.py` (OpenCV رباعي) 12/46 IoU>0.5، `lab/exp_coarse2fine.py` (محدِّد خشن→دقيق على الصورة الكاملة) 13/46 مقابل A 22/46. مرفوض للشحن؛ الطريق = بيانات صناديق شاشة + تدريب على صور كاملة.
- repro: 19/46 A, wrong-confident 0 أُعيد إنتاجه في البيئة الجديدة (`eval_repro_2026-10-20.log`). الصور الـ49 في المستودع الخاص (49/49).
- **ADR-0006** مستودع خاص للبيانات `almaham-3-private-data` + `scripts/private_data.sh` (pull/push-49/push-erp/push-dir/status، تحقق sha256، دفعات ≤1.5 GB، فحص أسرار قبل كل push) + تحديث `setup-environment.md`.
- env: `.gitignore` يتجاهل `.toolchain/` (JDK17 + Android SDK محليان خارج git). تحقق البيئة الجديدة: Python 24/24، Kotlin 45/45، تصدير ONNX مطابق بالبت لـ assets.

## [Unreleased] — 2026-10-18 جلسة A الأخيرة
- e2e 0→19/46 عبر ضبط دقيق على ERP (ft2–ft4) + إصلاح حدّ الكسر؛ غلط-وواثق 0.
- docs: PLAN.md، SUCCESSOR-AGENT.md، train-digitnet.md كامل، ADR-0005، برومتات B.
- tests: قاعدة 6 خانات (Python 11/11، Kotlin 45/45).

## [0.1.0-alpha] — 2026-10-18 — النسخة الأولية التجريبية (`v0.1.0`)
- APK تجريبي على GitHub Release؛ 49 اختبار وحدات؛ صلاحية CAMERA فقط. الأرقام والحدود في `docs/release-0.1.0.md`.

## [Unreleased] — 2026-10-18 (جولة 2، فرع genspark_ai_developer)
- meterocr: `MeterReader.read/close` @Synchronized؛ إزالة INTERNET/ACCESS_NETWORK_STATE ومزوّد التيليمتري من AAR ONNX Runtime عند دمج الـ manifest (offline فعلياً).
- lab/train_det.py: حفظ نقطة وتقييم كل 250 خطوة (كان 500).
### Added
- `docs/manifests/` (سجل البناء والهاشات، إعداد AVD)، `docs/history/2026-10-18-session-02-agentB.md`، `scripts/verify_app_build.sh` (وكيل B).
- demo: autobench intent، CaptureLog، rectcheck، x86_64 في debug؛ إصلاح كراشين (وكيل B). `docs/phone-test-emulator_x86_64_api30.md`.
- `app/meterocr/.../ForensicReader.kt` + `ForensicReaderTest.kt` + مثبّتات `test/resources/forensic/` + `lab/make_forensic_fixtures.py` (وكيل B).
- `benchmark/data/digit_boxes.json` + `digit_spans_manual.json` + `lab/make_digit_boxes.py` (وكيل B، عقد §3).
- `lab/forensic_reader.py` + `lab/eval_forensic_reader.py` (وكيل B، عقد §2).
- `app/`: مشروع Android (Kotlin + Compose + CameraX 1.5.0 + ONNX Runtime 1.31): موديول `meterocr` (config, RectGeometry, ReadingAssembler,
  ReadingValidator, PeakDecoder, MeterReader, EvidenceImage, ReadingLog) + تطبيق `demo` (شاشة إدخال، كاميرا بمستطيل/زوم/فلاش/ZSL،
  خط معالجة بعد الضغطة، وضع اختبار جماعي A/B × DigitNet/ML Kit). 35 اختبار وحدات.
- `lab/synth2.py` مولّد مشاهد بصناديق لكل رقم (DSEG OFL + إجرائي)، `det_model.py` DigitNet، `train_det.py`, `gen_det_data.py`,
  `assemble.py` (+10 اختبارات)، `export_onnx.py`, `eval_e2e.py`, `eval_reader_oracle.py`, `report.py`.
- وثائق: `docs/research/research_decision_v3.md`, `docs/benchmark_report.md` (+tables), `docs/migration-plan.md`, `app/README.md`.
### Measured
- DigitNet v1 (تدريب جزئي): 0/46 end-to-end، 3/46 قارئ فقط على قصّ مثالي، p50 50ms على CPU x86. التفاصيل في benchmark_report.md.

# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

## [Unreleased]
### Added
- مختبر جنائي: `lab/sevenseg4.py` `sevenseg5.py` `sevenseg6.py` `forensic_grid.py` + `docs/research/forensic-lab-2026-10-18.md`.
- `docs/research/how-they-do-it-2026-10-18.md`: تحليل Anyline/Laroca/MDPI + الحل المقترح + خطة تدريب على صور ERP المعتمدة.
- `scripts/export_erp_training.sql`: تصدير القراءات `confirmed` مع مفاتيح الصور (الجزء الصحيح فقط).
- `docs/brief/04_برومت_الوكيل_المفتوح.md`: برومت مفتوح لوكيل خارجي (يشرح الهدف والقيود والمعايير بدون فرض طريقة).

## [0.1.0] - 2026-10-18
### Added
- المستودع بهيكل cortex-memory: README, AGENTS/CLAUDE, STATUS, LESSONS, CONTRIBUTING, SECURITY, ADRs, REQ-001،
  تصميم الـ pipeline، runbooks، postmortem، سجل الجلسة.
- `docs/brief/`: المهمة الأصلية (الشرح، البرومت، البحوثات، صور التصميم — مع تمويه بيانات المشترك).
- `benchmark/data/`: ground_truth v2 (49 صورة)، meter/display/line boxes، بصمات SHA256 للصور.
- `benchmark/results/`: مخرجات PP-OCRv5/v6 و ERP baseline و SegReader + `verified_2026-10-18.txt`.
- `lab/`: كود البحث والتدريب، `paths.py` (مسارات موحّدة)، `eval_rec.py`، أوزان SegReader (s1000 و s4000)، سجلات التدريب.
- `scripts/`: `download_models.sh` (SHA256 مثبّت)، `verify_photos.sh`، `check.sh`. `requirements-lab.txt` بإصدارات مثبّتة.
### Changed
- `lab/gt.py` يقرأ ground_truth v2 (كان v1). كل المسارات المطلقة استُبدلت بـ `paths.py`.
- `train_rec.py`/`train_fast.py`: خيوط افتراضية 2 (كانت 3) وطباعة الأمر في أول سطر من السجل.
### Fixed
- 3 قراءات غلط في ground_truth v1 (23106, 23109, 23113) + 23086, 23091, 23072. انظر LESSONS.
### Deprecated
- `benchmark/data/archive/ground_truth_v1.csv`، `docs/research/archive/research_decision_v1.md`، `benchmark/results/archive/`.
- 2026-10-18 agent B: v0.1.1 pre-release = ONE APK only (owner): almaham-meter-0.1.1-arm64.apk, field, 37,849,126 B, sha256 9eaf497e…145e5c (stat/aapt2 native-code arm64-v8a). armv7/bench not published. ≤20 MB not reached: ORT 1.31 = 34,208,672 B; minimal ORT .so built 2,455,568 B but needs .ort assets (agent A). R8 build not yet run on device.
- 2026-10-18 agent B: docs — docs/apk-size-report.md (all byte tables, commands, ORT-minimal 2,455,568 B, LiteRT 4,320,480 B, parity 10/10), handoff docs/handoff/agentB-to-agentA-apk-size-0.1.1.md, release-0.1.0 §2 install note, app-build-record 0.1.1, artifacts/ort-minimal AAR.
- 2026-10-18 agent B: lab/multi_algo.py 792 deterministic exams (colours×polarity×binarizers×movements)+vote: line crop 20/46 (holdout 13/36; was 11/46), full meter rect 0/46. Not in app. docs/research/multi-algo-2026-10-18.md
- 2026-10-18 agent B: v0.2.0 pre-release — ONE APK arm64, 7,682,029 B, sha256 c6586916…906e7d, ORT 1.23.2 minimal + .ort (latest models 0735b8a/72d5c26), parity 49/49, CAMERA only, debug-signed, NOT run on a device after R8. docs/release-0.2.0.md
- 2026-10-18 agent B (GenCode-APK): v0.2.1 pre-release — model ft4a (8347475) converted .ort, parity 49/49, exact 19/46; ONE APK arm64 7,682,409 B sha256 8940f737…be3b3f, cert SHA-256 04f129a9…74a3 (debug). Not run on a device. Full build guide: GenCode-APK/README.md

### 2026-10-21 — ZBook tunnel + optical2 handoff
- `lab/zbook/{setup_tunnel_vps,bootstrap_zbook,check_zbook}.sh`: third training machine via reverse SSH tunnel (forward-only VPS user, limited ZBook user). Keys never in git; filled bootstrap only on the VPS behind a one-off token.
- `lab/webdemo/server.py`: `/dl?f=&t=` token-gated private download route (env `DL_DIR`, `DL_TOKEN`); 404 otherwise. Deployed.
- `docs/handoff/prompt-for-optical2-2026-10-21.md`: paste-ready tasks for the second agent (loss-masking experiment; Android capture hardening).

### 2026-10-24 — Astra r2 review
- `docs/handoff/review-of-optical2-r2-2026-10-24.md`: independent recount of optical2 @aca3e59 parity JSON (A 49/49, B 49/49 from original JPEG; pixels 196/196 ≤1; timing +10.86/+2.14 ms median, +20.29/+9.22 worst). Parity fix accepted; no ship, no gate merge.
- `docs/handoff/prompt-for-optical2-2026-10-24-r3.md`: next task for Astra — close the timing gap (≤+5 ms locator, ≤+2 ms reader) without breaking 49/49.
