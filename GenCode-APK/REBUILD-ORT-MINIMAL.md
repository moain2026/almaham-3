# إعادة بناء ONNX Runtime المصغّر (وكيل B / GenCode-APK)

**متى؟** فقط إذا تغيّرت قائمة العوامل (diff في README §4.1 غير فارغ)، أو لمعمارية أخرى (armv7).

## المتطلبات
- مصدر ORT **v1.23.2**: `git clone --depth 1 --branch v1.23.2 --recursive https://github.com/microsoft/onnxruntime.git`
  (≈ 730 MB بعد حذف `.git`). حتى تتغير، أبقِ 1.23.2: التحويل يجب أن يكون بنفس الإصدار.
- Android SDK + NDK **27.0.12077973**، JDK 17، **cmake ≥ 3.28** (`pip install cmake` → 4.4.4)، ninja، Python 3.
- ≈ 3 GB مساحة حرة للبناء (امتلأ القرص عندي في آخره).

## الأمر (= `artifacts/ort-minimal/run_build.sh`)
```bash
cd onnxruntime
python3 tools/ci_build/build.py --build_dir ../build_arm64 --config MinSizeRel \
  --android --android_sdk_path $ANDROID_HOME --android_ndk_path $ANDROID_HOME/ndk/27.0.12077973 \
  --android_abi arm64-v8a --android_api 24 \
  --minimal_build extended --include_ops_by_config <required_operators_and_types.config> \
  --disable_exceptions --disable_rtti --disable_ml_ops --enable_reduced_operator_type_support \
  --build_shared_lib --build_java --skip_tests --parallel 3 --cmake_generator Ninja \
  --cmake_path /usr/local/bin/cmake --skip_submodule_sync --allow_running_as_root
```
- المدة عندي: ≈15 دقيقة (1023 خطوة، 4 أنوية).
- الناتج: `build_arm64/MinSizeRel/java/build/android/outputs/aar/onnxruntime-release.aar`.
- الـ config: من `convert_onnx_models_to_ort --enable_type_reduction` (ملف `required_operators_and_types.config`).

## العوامل الحالية (16)
`ai.onnx`:
- opset 11: Conv
- opset 12: MaxPool
- opset 13: Cast(bool→float)، Clip، Equal، ReduceMean، Resize، Sqrt، Transpose
- opset 14: Add، Div، Mul، Sub

`com.microsoft`: FusedConv.

كلها float فقط.

## بعد البناء
1. انسخ الـ AAR إلى `artifacts/ort-minimal/maven/com/almaham/ort/onnxruntime-minimal-arm64/<ver>/onnxruntime-minimal-arm64-<ver>.aar` (+ pom بنفس النمط).
2. لو تغيّر الإصدار: غيّر السطر في `app/meterocr/build.gradle.kts` (يحتاج موافقة وكيل A).
3. حدّث `artifacts/ort-minimal/SHA256SUMS` و`benchmark/results/size/ort_required_operators_and_types.config`.
4. تطابق 49/49 ثم بناء ثم نشر. الـ commit يبدأ بـ `build(meterocr):`.
5. احذف مجلد البناء (يأكل القرص).

## لـ armv7 (غير مبني)
نفس الأمر مع `--android_abi armeabi-v7a --build_dir ../build_armeabi-v7a`، ثم AAR ثانٍ أو دمج `jni/` في AAR واحد، ثم `include("arm64-v8a","armeabi-v7a")` في splits.
