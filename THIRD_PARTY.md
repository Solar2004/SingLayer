# Upstream software

SingLayer is integration code, not a replacement music player or lyric engine.
Submodules preserve the upstream repositories and licenses at pinned commits.

| Component | Role | License | Included in default runtime? |
|---|---|---|---|
| [WebNowPlaying](https://github.com/keifufu/WebNowPlaying) | Browser detection and playback controls | MIT | Install official extension separately |
| [Kotonoha](https://github.com/locez/kotonoha) | Entire overlay, lyrics lookup/cache, manual search, word highlighting, native Wayland bridge | MIT; native blur protocol LGPL-2.1-or-later | Yes |
| [SongRec](https://github.com/marin-m/SongRec) | Shazam recognition | GPL-3.0 | Optional separate application |
| [ShazamIO](https://github.com/shazamio/ShazamIO) | Recognition fallback when SongRec is not installed | MIT | Optional `engines` extra |
| [syncedlyrics](https://github.com/moehmeni/syncedlyrics) | Musixmatch, Megalobiz and plain Genius lyrics | MIT | Optional `engines` extra |
| [SyncLyrics](https://github.com/AnshulJ999/SyncLyrics) | Evaluated lyrics server and alternative frontend | MIT + Commons Clause | No; reference submodule only |

SingLayer's MIT license does not relicense these dependencies. Do not describe
SyncLyrics as unrestricted MIT or bundle it into a commercial distribution without
reviewing its Commons Clause. SongRec remains a separately invoked application.
Kotonoha's build ships its license texts. Python dependencies retain their licenses.

The browser wire contract is implemented from WebNowPlaying's revision-3 protocol
(`src/extension/sw/socket.ts` and `src/extension/sw/port.ts`). No extension source
or lyric renderer has been copied into SingLayer's original package.

Lyrics are retrieved by upstream providers at runtime. No song lyrics, media,
user caches or credentials are committed to this repository.

The panel imports Kotonoha's native LRCLIB/NetEase/KuGou providers, LRC parser and
Wayland blur wrapper unchanged. It sends source-neutral documents using Kotonoha's
documented adapter protocol. Browser icons come from the user's installed icon theme.
NumPy supplies FFT processing. FFmpeg and `parec` are separate system executables.
Library licenses do not grant rights to redistribute providers' lyric catalogs.

Local Whisper installation uses [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
(MIT), pinned to `60c0be6ac8fa71b1a2ae2dd938a31a34a508e774`, and the
multilingual Whisper base model distributed by its maintainers (MIT). Vulkan
builds use Khronos Vulkan-Headers (Apache-2.0/MIT) and SPIRV-Headers (MIT),
with original license files retained in `.build/`. Scripts reuse the installed
Vulkan loader and driver; they do not redistribute or replace the driver.

Local pronunciation uses espeakng-loader 0.2.4, which loads eSpeak NG
(GPL-3.0-or-later), langid 1.1.6 (BSD), and pykakasi 2.3.0
(GPL-3.0-or-later). These libraries retain their upstream licenses; SingLayer's
MIT license does not relicense them. Distribution of a combined application must
account for the GPL dependencies and include corresponding license/source
obligations. The ShazamIO fallback runs in a separate Python 3.12 environment to
avoid a reproduced native-extension crash on Python 3.14.

Current ASR integration is [CrisperWhisper2.0](https://github.com/nyrahealth/CrisperWhisper),
code MIT, with its CTranslate2 fork (MIT) and Transformers/PyTorch conversion
runtime retaining their licenses. **The2.0 model weights are under Nyra Health
Non-Commercial Research License, not MIT**; commercial use requires appropriate
licensing. Models are downloaded during setup, not bundled. The user later authorized Whisper.cpp as an alternative; large-v3-turbo Q5_0
(MIT Whisper weights) is now the validated RX590 Vulkan runtime. Its pinned source,
model revision and verified SHA256 are in docs/AUTOMATIC_TIMING.md. Crisper CPU
remains explicitly selectable; its non-commercial model license is unchanged.

Full-track downloading uses the separately installed [yt-dlp](https://github.com/yt-dlp/yt-dlp) 2026.8.19 (Unlicense), with its official default dependencies retaining their upstream licenses. FFmpeg remains a separate system executable; Node is used when available for JavaScript extraction. No downloaded music is bundled or committed.

The pinned whisper.cpp build applies the local MIT patch in `patches/whisper-reuse-language-encoder.patch`; upstream remains MIT. See docs/ENCODER_REUSE.md for source revision, build validation and measured preservation of output.
