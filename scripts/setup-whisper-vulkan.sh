#!/usr/bin/env bash
# Opt-in AMD backend. Readiness requires an actual inference using Vulkan.
set -euo pipefail
cd "$(dirname "$0")/.."
for executable in git cmake glslc curl sha256sum rg; do
  command -v "$executable" >/dev/null || { echo "Missing dependency: $executable" >&2; exit 1; }
done
revision=60c0be6ac8fa71b1a2ae2dd938a31a34a508e774
source_dir=.build/whisper.cpp
if [[ ! -d "$source_dir/.git" ]]; then
  git clone https://github.com/ggml-org/whisper.cpp.git "$source_dir"
  git -C "$source_dir" checkout --detach "$revision"
fi
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$revision" && -z "$(git -C "$source_dir" status --porcelain)" ]] || {
  echo 'Expected clean pinned whisper.cpp checkout; existing work was not changed.' >&2; exit 1;
}
patch_file="$PWD/patches/whisper-reuse-language-encoder.patch"
git -C "$source_dir" apply --check "$patch_file"
git -C "$source_dir" apply "$patch_file"
# The pinned upstream checkout remains clean after success or build failure.
trap 'git -C "$source_dir" apply --reverse "$patch_file"' EXIT
options=(-DGGML_VULKAN=ON -DGGML_CUDA=OFF -DWHISPER_CURL=OFF -DCMAKE_BUILD_TYPE=Release)
if [[ -f .build/Vulkan-Headers/include/vulkan/vulkan.h && -d .build/vulkan-sdk/include/spirv ]]; then
  options+=("-DVulkan_INCLUDE_DIR=$PWD/.build/Vulkan-Headers/include"
            "-DCMAKE_PREFIX_PATH=$PWD/.build/vulkan-sdk"
            "-DCMAKE_CXX_FLAGS=-I$PWD/.build/vulkan-sdk/include")
fi
cmake -S "$source_dir" -B .build/whisper-vulkan "${options[@]}"
cmake --build .build/whisper-vulkan --target whisper-server whisper-cli -j 4
mkdir -p .build/models .build/whisper
model=.build/models/ggml-large-v3-turbo-q5_0.bin
checksum=394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2
if [[ ! -f "$model" ]]; then
  curl --fail --location --retry 3 --continue-at - --output "$model.part" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-large-v3-turbo-q5_0.bin
  printf '%s  %s\n' "$checksum" "$model.part" | sha256sum --check
  mv "$model.part" "$model"
fi
printf '%s  %s\n' "$checksum" "$model" | sha256sum --check
.build/whisper-vulkan/bin/whisper-cli -m "$model" -f "$source_dir/samples/jfk.wav" \
  --language auto --no-flash-attn --dtw large.v3.turbo -t 4 -oj -of .build/whisper/smoke >.build/whisper/smoke.log 2>&1
# A compiled Vulkan option alone is not proof of device execution.
rg 'using Vulkan[0-9]+ backend' .build/whisper/smoke.log >/dev/null
.venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path
root = Path.cwd()
result = json.loads((root / '.build/whisper/smoke.json').read_text())
if not result.get('transcription'):
    raise SystemExit('Whisper produced no speech in the baseline fixture')
config = {'backend': 'whisper.cpp', 'device': 'vulkan', 'model': 'large-v3-turbo-q5_0',
          'binary': str(root / '.build/whisper-vulkan/bin/whisper-server'),
          'model_path': str(root / '.build/models/ggml-large-v3-turbo-q5_0.bin'),
          'source_revision': '60c0be6ac8fa71b1a2ae2dd938a31a34a508e774',
          'model_revision': '5359861c739e955e79d9a303bcbc70fb988958b1',
          'sha256': '394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2',
          'inference_profile': 'reuse-language-encoder-v1',
          'build_patch_sha256': hashlib.sha256((root / 'patches/whisper-reuse-language-encoder.patch').read_bytes()).hexdigest(),
          'library_path': str((root / '.build/whisper-vulkan/bin/libwhisper.so').resolve()),
          'library_sha256': hashlib.sha256((root / '.build/whisper-vulkan/bin/libwhisper.so').read_bytes()).hexdigest()}
path = root / '.build/whisper/ready.json'
temporary = path.with_suffix('.part')
temporary.write_text(json.dumps(config, indent=2))
temporary.replace(path)
print('Whisper.cpp Vulkan validated and selected; restart SingLayer.')
PY
