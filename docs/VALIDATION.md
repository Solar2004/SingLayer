# Validation — 2026-10-04, CrisperWhisper migration

**98 passed, 4 deselected**; Ruff, shell syntax and git diff --check pass.

The panel no longer calls whisper.cpp. The dedicated CrisperWhisper service and
transport preserve word timestamps into the native overlay. Offline proofs cover
acoustic-language detection dispatch, PCM input, exact word spans after browser
anchoring, grouping/spacing including CJK, malformed/overlapping/out-of-window
spans, exact catalog word preservation, cancellation and bounded capture queues.
Service inference is tested with a substitute model, not real model weights.

Actual installation failed fetching torch due DNS in this restricted session;
network permission was requested and not granted. No real CrisperWhisper inference
or performance benchmark has run. Four IPC tests remain excluded because sockets
and D-Bus are denied; repeat full suite with IPC access. No GPU speed claims apply
to CrisperWhisper. The older Vulkan benchmark belongs to whisper.cpp only.

See CRISPERWHISPER.md for install/status and HANDOFF.md for continuation.
