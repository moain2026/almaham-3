#!/usr/bin/env bash
# Minimal ONNX Runtime for Android arm64 with only our models' operators (agent B, docs/apk-size-report.md)
cd /home/user/ortbuild/src
export ANDROID_HOME=/home/user/android-sdk ANDROID_NDK_HOME=/home/user/android-sdk/ndk/27.0.12077973
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
nice -n 10 python3 tools/ci_build/build.py --build_dir /home/user/ortbuild/build_arm64 --config MinSizeRel \
  --android --android_sdk_path $ANDROID_HOME --android_ndk_path $ANDROID_NDK_HOME --android_abi arm64-v8a --android_api 24 \
  --minimal_build extended --include_ops_by_config /home/user/ortbuild/required_operators.config \
  --disable_exceptions --disable_rtti --disable_ml_ops --enable_reduced_operator_type_support \
  --build_shared_lib --build_java --skip_tests --parallel 3 --cmake_generator Ninja \
  --cmake_path /usr/local/bin/cmake --skip_submodule_sync --allow_running_as_root
echo BUILD_EXIT $?
