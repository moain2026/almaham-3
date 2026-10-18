# R8 keep rules for the demo app (release). Verified on device/emulator after shrinking (docs/apk-size-report.md).
# ONNX Runtime: JNI calls back into Java classes by name.
-keep class ai.onnxruntime.** { *; }
-dontwarn ai.onnxruntime.**
# Our engine library is called from JNI-free Kotlin only, but keep its public API readable in crash logs.
-keep class com.almaham.meterocr.** { *; }
# CameraX / Camera2 interop uses reflection for quirks.
-keep class androidx.camera.camera2.** { *; }
-dontwarn androidx.camera.**
# ML Kit (bench flavor only).
-dontwarn com.google.mlkit.**
-keepattributes SourceFile,LineNumberTable
