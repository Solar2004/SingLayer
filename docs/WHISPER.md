# Local Whisper: Vulkan and CPU

The multilingual base model is installed and SHA-256 verified. whisper.cpp is
pinned to `60c0be6ac8fa71b1a2ae2dd938a31a34a508e774`.

**Historical benchmark only:** the Whisper base runtime was replaced by
CrisperWhisper at the user's request. The old setup/run scripts were removed;
these measurements do not establish CrisperWhisper GPU support. See
[CRISPERWHISPER.md](CRISPERWHISPER.md) and [GPU.md](GPU.md).

Current hardware now accessible outside the old sandbox: Vulkan identifies
**AMD Radeon RX 590 GME (RADV POLARIS10)**, Mesa 26.1.8, device 1002:6fdf.
The generic PCI database label is RX580 2048SP; Vulkan provides the RX590 GME name.
`shaderFloat16=false`; use measured results instead of assuming modern-GPU speed.

The panel starts the persistent Vulkan server when last-resort transcription or
edited-version alignment is enabled after lyric search. The worker captures
12-second browser windows with an 8-second hop, one queued window, and one
inference at a time. Pauses, seeks, track changes and stream changes invalidate
capture. Invalid model timestamps discard a window without terminating the
session. Audio matching accepts only distinctive catalog phrases; repeated
choruses are rejected. This does not guarantee automatic timing for every remix.

Upstream: https://github.com/ggml-org/whisper.cpp (MIT).
Its existing whisper-server keeps the model loaded and accepts WAV files at
`/inference`. CPU and Vulkan backends exist. Use a multilingual model, not `.en`.
Language auto-detection is supported; coverage and quality are not all languages
equally, and singing/mixed vocals may be inaccurate.

Implemented integration boundary: last-resort local ASR, browser-isolated PCM only,
one inference at a time, bounded rolling windows with overlap and timestamp-based
deduplication. Cancel on pause/seek/track change. Keep a persistent loaded model
instead of restarting whisper-cli for every chunk. Label output as estimated
transcription, not verified lyrics. Do not translate automatically.

Timing must anchor each audio window to the browser clock at capture time, not
at inference completion. Live results inevitably arrive after the captured words;
they cannot provide advance karaoke lyrics on the first pass. A later replay can
use already-transcribed spans. Entire-song capture starts only when listening
starts; absent earlier audio cannot be reconstructed without obtaining a file.

Benchmark gate before enabling automatically: model load succeeds on the actual
GPU; report backend/device, model, window length, inference time and total display
delay. Try CPU only as an explicitly identified fallback, never call it GPU.
Do not promise RX 590 compatibility based solely on Vulkan being supported.

Historical `/dev/dri`/DNS failures came from the earlier restricted environment;
GPU and network were revalidated after access changed. See HANDOFF.md for the
latest benchmark and remaining app integration work.

## Hardware benchmark, 2026-10-03

Real persistent HTTP servers, same multilingual base model, four CPU threads,
three sequential requests per backend. Input: upstream `samples/jfk.wav`, 11 s
spoken English. Each request passed through SingLayer `transcribe_window`, with
capture anchor 40 s; parser accepted both outputs and text was identical.

| Backend | First request | Second | Third |
|---|---:|---:|---:|
| CPU | 4.206 s | 4.275 s | 4.256 s |
| RX590 GME / Vulkan | 1.584 s | 1.007 s | 1.036 s |

About 4.2x faster for subsequent GPU requests. Server ready in ~1 s on both
backends, measured with 0.5 s polling. GPU log explicitly reports `using Vulkan0
backend`, with 147.37 MB of model weights on Vulkan0. This is a single speech
fixture, not a singing/multilingual accuracy study or an end-to-end live latency
claim. Audio acquisition adds its own duration. Test servers were stopped cleanly.

Raw local evidence: `.build/benchmarks/results.json`, `cpu-server.log`,
`vulkan-server.log`. These generated files are intentionally not versioned.
