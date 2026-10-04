# CrisperWhisper on RX590: investigation and next proof

2026-10-04. **Not yet working or validated on GPU.** Current integrated backend
is CrisperWhisper2.0 Python/CTranslate2 CPU int8, and it is not installed yet.

## Findings from source, rather than package names

The official Python runtime supports CPU/CUDA; it provides no Vulkan backend.
[Saganaki22/CrisperWhisper.cpp](https://github.com/Saganaki22/CrisperWhisper.cpp)
is a community implementation using ggml and whisper.cpp with CrisperWhisper's
actual tokenizer, prompt and supervised word timing. Its distributed binaries
are CPU or NVIDIA CUDA, not AMD Vulkan binaries.

Its [CMakeLists.txt](https://github.com/Saganaki22/CrisperWhisper.cpp/blob/main/CMakeLists.txt)
forces GGML_CUDA from CRISPERWHISPER_CUDA but does not force GGML_VULKAN off.
It fetches whisper.cpp at080bbbe85230f624f0b52127f1ae1218247989f9 and applies a
cross-attention patch. Its [model source](https://github.com/Saganaki22/CrisperWhisper.cpp/blob/main/src/crisperwhisper.cpp)
passes use_gpu/gpu_device into both inference and timing contexts; timing disables
flash attention. **Inference:** compiling the dependency with Vulkan is a plausible
route, but this is not upstream-tested RX590 support. The attention patch and
Vulkan operations still need real verification. Stock whisper.cpp conversion
alone is insufficient for CrisperWhisper's extra control tokens.

## Prepared experiment

```sh
bash scripts/build-crisper-vulkan.sh
```

This attempts community release v1.2.0, disables CUDA, enables GGML_VULKAN,
requires a generated ggml-vulkan target, builds and runs native tests. It refuses
dirty or unexpected checkouts. Source downloads and compilation have NOT run
here because GitHub DNS is denied. Shell syntax was checked. Record the resolved
release commit before relying on a successful future build. This script does
not install a model, alter the panel backend or mark the GPU ready.

Next obtain the small GGML model and adjacent metadata from the community
[converted-model repository](https://huggingface.co/drbaph/CrisperWhisper2.0-GGML),
or convert the official small checkpoint with upstream's converter. Pin repository
revision and verify the download's hash. Keep weights out of Git; retain model
license and metadata alignment-head/suppression settings.

With an authorized audio fixture, inspect the built CLI's --help and run it with
--word-timestamps --json --no-flash-attn, the model, audio and explicit language.
The community CLI defaults to English: do not mistake this for automatic language
detection. Log real backend/device and verify both inference and timing contexts
use Vulkan, not silent CPU fallback. Compare word boundaries, speed, memory and
output against CPU. Repeated tests must retain the model in memory: the CLI loads
on each invocation and is unsuitable as the final per-window production caller.

Only after that gate, add a persistent C++ API service reusing one Model and the
existing loopback transport contract (language and word/start/end objects). Check
language detection, cancellation, bounded inference, health backend identity and
music variants before changing the panel. Do not activate a flag-only GPU mode.

## Current access and older evidence

This session cannot resolve github.com and does not expose /dev/dri. Additional
network/device access was requested and not granted. Thus no fresh AMD benchmark
or C++ build is possible here. An earlier unrestricted session proved Vulkan on
RX590 GME for ordinary whisper.cpp base (see WHISPER.md); that does not establish
CrisperWhisper compatibility. No drivers or device permissions were changed.
