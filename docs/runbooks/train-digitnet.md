# Runbook: تدريب DigitNet (المحدِّد + القارئ) وتصديره للتطبيق
**متى:** بعد أي تغيير في `synth2.py` أو لإكمال التدريب · **العتاد:** CPU يكفي لكنه بطيء (~0.8s/خطوة قارئ، ~1.5s/خطوة محدِّد بخيطين)؛ GPU يختصر 20×.

1. توليد البيانات (كل أمر ~15 دقيقة لـ 16k سطر أو 12k مشهد، عاملان):
   `cd lab && python3 gen_det_data.py line 16000 ../data/synth/line_a 11 && python3 gen_det_data.py scene 12000 ../data/synth/scene_a 21`
   (كرّر بـ `line_b 12`، `scene_b 22` لمزيد من التنوع.)
2. التدريب (في الخلفية، خيطان):
   `TORCH_THREADS=2 nohup python3 train_det.py reader 40000 weights/reader_v2.pt ../data/synth/line_a,../data/synth/line_b > logs/train_reader_v2.log 2>&1 &`
   `TORCH_THREADS=2 nohup python3 train_det.py locator 20000 weights/locator_v2.pt ../data/synth/scene_a,../data/synth/scene_b > logs/train_locator_v2.log 2>&1 &`
   السجل يطبع `val` على هولد-أوت اصطناعي كل 500 خطوة (القارئ: مطابقة الرقم الصحيح؛ المحدِّد: IoU>0.5).
3. فحص القارئ وحده على الصور الحقيقية: `python3 eval_reader_oracle.py weights/reader_v2.pt`.
4. التصدير والتحقق من التطابق: `python3 export_onnx.py weights/locator_v2.pt weights/reader_v2.pt ../app/meterocr/src/main/assets/models`.
5. القياس end-to-end: `python3 eval_e2e.py ../app/meterocr/src/main/assets/models v2 && python3 report.py v2 > ../docs/benchmark_report_tables.md`.
6. بناء APK: `cd ../app && JAVA_HOME=/path/jdk17 ./gradlew :demo:assembleDebug`.

**قاعدة:** الـ49 صورة لا تدخل أي خطوة قبل 3. عتبات `CONFIG` لا تُضبط عليها.
