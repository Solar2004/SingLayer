# Lyrics and alignment reuse

Reviewed 2026-10-03:

- Follow-up specific to SoundCloud: https://github.com/coolnerdave/cloudlyrics
  implements synced SoundCloud lyrics using LRCLIB, a mini panel and fullscreen
  view. Not previously included in the research, not integrated; it does not
  constitute a new lyrics catalog beyond LRCLIB already used by SingLayer.
- https://github.com/romaniv1437/chromic-extension also targets SoundCloud with a
  visualizer and word-synced lyrics. Discovered in the follow-up, not integrated
  or verified for coverage; README claims are not evidence of universal success.
- PulseAudio upstream `src/utils/pactl.c` explicitly serializes sink monitor
  names as `monitor_source`. SingLayer incorrectly required `monitor_source_name`;
  fixed with a test using the real JSON key, retaining compatibility with both.

- https://github.com/moehmeni/syncedlyrics — already integrated; Musixmatch enhanced
  word timing when available, other catalogs and plain-text fallback. No universal
  coverage guarantee. Avoid duplicating its providers as nominally new engines.
- https://github.com/chenmozhijin/LDDC — GPL-3.0, approximately 1.8k stars at review;
  QQ, KuGou, NetEase and LRCLIB, word-timed formats. Not integrated in this update:
  adds application/runtime and license boundaries, overlaps existing providers,
  and does not itself align arbitrary slowed browser audio automatically.
- https://github.com/iamjrmh/usersync — local audio-file alignment using WhisperX,
  whisper.cpp and Demucs; candidate for a later explicit local-file alignment
  workflow, not a verified lightweight live-browser solution. Not integrated.

No verified published hit rate supports promising every song or every remix.
Current selection still accepts the first successful timed result; it is not a
cross-provider accuracy ranking or an audio-validated synchronization algorithm.
Automatic slowed/remix alignment remains unfinished rather than guessed.

ChatJimmy wire protocol was inspected in the user-designated local Rust proxy.
SingLayer implements a small independent client for that protocol, not a bundled
copy of the proxy source. Its system skill is packaged with the Python module.
