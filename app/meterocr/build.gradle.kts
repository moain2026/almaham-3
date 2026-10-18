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
    androidResources { noCompress += listOf("onnx", "ort") }
    testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
    // ONNX Runtime 1.23.2 MINIMAL build (MIT), arm64-v8a only, only our models' operators; loads .ort models. docs/apk-size-report.md
    api("com.almaham.ort:onnxruntime-minimal-arm64:1.23.2")   // artifacts/ort-minimal/maven (AGP rejects files("*.aar") in a library)
    api("androidx.exifinterface:exifinterface:1.3.7")
    testImplementation("junit:junit:4.13.2")
}
