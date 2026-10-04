# SingLayer readiness — 2026-10-04

## Verified

- 118 full tests pass, no exclusions; Ruff, shell syntax and diff checks pass.
- Real desktop panel, bridge and Kotonoha launch; Brave WebNowPlaying connects.
- Browser stream capture and ShazamIO work. Honeypie slowed/bass edition produced
  3/3 matching recognitions; Coldplay was also recognized during autoplay.
- Fixed recognized-edition catalog lookup. The observed Honeypie identity now
  reaches JAWNY's 28 synced LRCLIB lines using real catalogs. Those lyrics retain
  candidate status until audio/clock alignment establishes the correspondence.
- Local pronunciation generated28 English guide lines for Honeypie; fixed short
  repetitive refrains that langid misclassified despite an English song context.
- Official CrisperWhisper small is installed, converted to CT2 CPU int8 and pinned
  to bcaecf0a584a1f600d8897fe6032b9e2e56429a7. Readiness checks acoustic language
  detection; restored native metadata fixes the observed detect_language failure.
- Real local API: JFK11s audio, English detected,22 words,4 valid adapter lines,
  8.56s inference. The existing100ms boundary tolerance handles a20ms final edge.
- Desktop launcher already points to `.venv/bin/singlayer app`. Panel left open.

- Native PipeWire capture now works when pactl cannot see the stream. Browser choice
  isolates Brave from other browser playback; muted or ambiguous streams are rejected.
- Metadata regression coverage includes pipes, bass boosted, 8D, numeric speed,
  slowed to perfection and TikTok suffixes.

## Still required before claiming everything is finished

- Repeat corrected Honeypie flow from the start without autoplay changing track.
- Actual singing matrix now exists (docs/MUSIC_VALIDATION.md). Small CPU recognizes
  some English/Japanese words but returns empty or inaccurate fragments on others;
  automatic edited-song alignment remains unproven. Repeated choruses stay ambiguous.
  CPU produces delayed observed words; it cannot provide future lyrics on first playback.
- CrisperWhisper GPU: Vulkan detects RX590, but original C++ source returns404.
  No compiled/verified AMD backend exists yet; CPU is clearly labelled as CPU.
- Inspect compositor blur and final visual behavior on real Wayland/X11. Offscreen
  tests and process launch do not prove every desktop visual detail.

No audio, complete lyrics or model weights are committed. Shazam recognition is
not a universal guarantee for every remix; catalog timing requires calibration
or observed alignment when the playback speed or structure changes.
