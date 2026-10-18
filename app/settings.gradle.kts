pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // ONNX Runtime minimal build (agent B, docs/apk-size-report.md) — local file repo, no network
        maven { url = uri("../artifacts/ort-minimal/maven") }
    }
}
rootProject.name = "almaham-meter"
include(":meterocr", ":demo")
