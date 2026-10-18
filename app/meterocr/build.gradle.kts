plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.almaham.meterocr"
    compileSdk = 35
    defaultConfig {
        minSdk = 24
        consumerProguardFiles("consumer-rules.pro")
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    // ONNX models are already compressed; keep them stored so they can be memory-mapped.
    androidResources { noCompress += listOf("onnx") }
    testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
    // ONNX Runtime for Android — MIT license. arm64-v8a / armeabi-v7a / x86_64 native libs, CPU (XNNPACK) + NNAPI EPs.
    api("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")
    api("androidx.exifinterface:exifinterface:1.3.7")
    testImplementation("junit:junit:4.13.2")
}
