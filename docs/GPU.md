# GPU RX590: estado actual e investigación histórica

## Ruta instalada y probada — 2026-10-04

El usuario autorizó otro motor probado para canciones. Whisper.cpp
large-v3-turbo Q5_0 funciona con Vulkan y DTW en RX590 GME/RADV POLARIS10.
`bash scripts/setup-whisper-vulkan.sh` reproduce la instalación y exige una
inferencia real con Vulkan antes de publicar ready.json. El servicio comprueba
el backend al iniciar. No se modificaron drivers.

Pruebas musicales, revisiones, hash y límites: [AUTOMATIC_TIMING.md](AUTOMATIC_TIMING.md).
CrisperWhisper small CPU permanece disponible explícitamente. Su ruta comunitaria
C++ sigue devolviendo404; no se afirma que Crisper funcione en GPU.

## Investigación anterior (restricciones ya superadas)

Lo siguiente documenta sesiones anteriores. Las afirmaciones de falta de red o
/dev/dri no describen el entorno actual, que permitió compilar y probar Whisper.

# CrisperWhisper on RX590: investigation and next proof

2026-10-04. **Not yet working or validated on GPU.** Current integrated backend
is CrisperWhisper2.0 Python/CTranslate2 CPU int8, now installed and tested on real speech.

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

## Continuation verification — 2026-10-04

Network access was granted in the continuation. GitHub fetch and push succeeded;
remote main was verified at d7ccb42c0cbb42c21cd11802b37f9fec3e394025.
The prepared build was attempted, but cloning the community repository failed
with `Repository not found`; the GitHub repository API also returned HTTP 404.
Cached search results are not proof that the source is currently downloadable.
Do not substitute an unverified mirror or claim a successful build.

Read permission for /dev/dri was granted, but the directory is still absent from
the execution environment. Permission alone does not expose the host GPU.
Vulkan inference and timing validation still require an environment with the
actual device and a verifiable source revision. No drivers were changed.

Regression check: 98 passed, 4 IPC-dependent tests deselected.

## Full-access validation — 2026-10-04

The host GPU is now exposed: vulkaninfo identified RX590 GME / RADV POLARIS10,
Mesa26.1.8. The absent-device note above describes the earlier sandbox only.
The source repository still returns HTTP404, so no Crisper Vulkan build or GPU
inference was verified. Official CPU runtime/model installation succeeded.
Real JFK API inference took8.56s for11s audio with22 words and detected English;
this is a CPU speech baseline, not a singing or AMD Crisper benchmark.
