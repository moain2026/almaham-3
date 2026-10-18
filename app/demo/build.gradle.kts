plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.almaham.meterdemo"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.almaham.meterdemo"
        minSdk = 24
        targetSdk = 35
        versionCode = 2
        versionName = "0.1.1"
        vectorDrawables.useSupportLibrary = true
    }
    buildTypes {
        release {
            // R8: shrink + obfuscate code and drop unused resources (docs/apk-size-report.md). Keep rules: proguard-rules.pro.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    // field = what readers install (no ML Kit). bench = same app + ML Kit baseline for the batch comparison.
    flavorDimensions += "use"
    productFlavors {
        create("field") { dimension = "use" }
        create("bench") { dimension = "use"; versionNameSuffix = "-bench" }
    }
    // One APK per CPU architecture instead of both in one file (phones: arm64-v8a, armeabi-v7a).
    // x86_64 only when building for the emulator: ./gradlew -Pemulator ...
    splits {
        abi {
            isEnable = true
            reset()
            if (project.hasProperty("emulator")) include("arm64-v8a", "armeabi-v7a", "x86_64")
            else include("arm64-v8a", "armeabi-v7a")
            isUniversalApk = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(project(":meterocr"))
    val camerax = "1.5.0"
    implementation("androidx.camera:camera-core:$camerax")
    implementation("androidx.camera:camera-camera2:$camerax")
    implementation("androidx.camera:camera-lifecycle:$camerax")
    implementation("androidx.camera:camera-view:$camerax")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    // Baseline comparison engine (brief §6.a). Google ML Kit: proprietary but royalty-free ("ML Kit Terms"); bundled model ~4MB.
    "benchImplementation"("com.google.mlkit:text-recognition:16.0.1")
    testImplementation("junit:junit:4.13.2")
}
