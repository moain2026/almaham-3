#!/usr/bin/env bash
# Rebuild the Android app, run all unit tests, and print the hashes to compare with docs/manifests/app-build-record.md.
# Usage: bash scripts/verify_app_build.sh   (needs JDK 17 + Android SDK 35; set SDK_DIR / JAVA_HOME if different)
set -euo pipefail
cd "$(dirname "$0")/../app"
SDK_DIR="${SDK_DIR:-/home/user/android-sdk}"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
echo "sdk.dir=$SDK_DIR" > local.properties
./gradlew --no-daemon -q :meterocr:testDebugUnitTest :demo:testDebugUnitTest :demo:assembleDebug
for f in meterocr/build/test-results/testDebugUnitTest/*.xml demo/build/test-results/testDebugUnitTest/*.xml; do
  grep -o 'testsuite name="[^"]*" tests="[0-9]*" skipped="[0-9]*" failures="[0-9]*" errors="[0-9]*"' "$f"
done
echo "--- model assets (must match the record exactly)"
sha256sum meterocr/src/main/assets/models/*.onnx
echo "--- APK (debug APKs are NOT byte-reproducible across machines/keystores; compare models + tests, not this hash)"
sha256sum demo/build/outputs/apk/debug/demo-debug.apk
