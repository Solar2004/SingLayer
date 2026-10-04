#!/usr/bin/env bash
# Experimental source build only. Does not install a model or activate the panel.
set -euo pipefail
cd "$(dirname "$0")/.."
for executable in git cmake glslc; do
  command -v "$executable" >/dev/null || { echo "Missing dependency: $executable" >&2; exit 1; }
done
source_dir=.build/crisperwhisper-cpp
build_dir=.build/crisper-cpp-vulkan
release=v1.2.0
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --depth 1 --branch "$release" https://github.com/Saganaki22/CrisperWhisper.cpp.git "$source_dir"
fi
[[ -z "$(git -C "$source_dir" status --porcelain)" ]] || {
  echo 'CrisperWhisper.cpp has local changes; refusing to overwrite them.' >&2; exit 1;
}
[[ "$(git -C "$source_dir" describe --tags --exact-match HEAD)" == "$release" ]] || {
  echo "Expected CrisperWhisper.cpp $release; use a separate checkout for other revisions." >&2; exit 1;
}
options=(-DCRISPERWHISPER_CUDA=OFF -DGGML_VULKAN=ON -DCRISPERWHISPER_BUILD_TESTS=ON
         -DCRISPERWHISPER_CPU_PROFILE=balance -DCMAKE_BUILD_TYPE=Release)
# Reuse local headers from the earlier Vulkan build when present.
if [[ -f .build/Vulkan-Headers/include/vulkan/vulkan.h && -d .build/vulkan-sdk/include/spirv ]]; then
  options+=("-DVulkan_INCLUDE_DIR=$PWD/.build/Vulkan-Headers/include"
            "-DCMAKE_PREFIX_PATH=$PWD/.build/vulkan-sdk"
            "-DCMAKE_CXX_FLAGS=-I$PWD/.build/vulkan-sdk/include")
fi
cmake -S "$source_dir" -B "$build_dir" "${options[@]}"
# Check generated target, not just the cached option: unused flags are not proof.
cmake --build "$build_dir" --target ggml-vulkan -j 4
cmake --build "$build_dir" -j 4
ctest --test-dir "$build_dir" --output-on-failure
printf 'Source revision: '
git -C "$source_dir" rev-parse HEAD
printf 'Experimental build only. Verify real Vulkan inference with --word-timestamps before activating it.\n'
