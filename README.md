# SingLayer

## Native panel update

Run **`.venv/bin/singlayer app`** for the current monochrome panel with cover art,
real browser-stream FFT and a single search status. Advanced controls live in **⋯**.
Close old panel/bridge/overlay instances before upgrading. The original `start`
command below remains a legacy MPRIS-only mode.

The new panel reuses Kotonoha's providers and canonical overlay adapter. It queries
LRCLIB/NetEase/KuGou concurrently, then tries syncedlyrics' Musixmatch/Megalobiz.
SongRec or ShazamIO recognition automatically overlaps during playback:
at most three sequential 12-second samples, at most four operations concurrently.
Pending work is cancelled on a result or track change. Genius is a labelled
plain-text fallback, never assigned invented timestamps. Session result caching,
manual title/artist correction, line selection, offset and speed are implemented.

The setup script installs engines by default; existing installs automatically
prepare missing engines on launch. Requires network access; direct versions are
in `requirements-engines.txt` (transitive dependencies not locked yet). `pactl`/`parec`
and native `pw-dump`/`pw-record` capture one selected browser playback stream,
never the desktop mix or microphone; ambiguous streams are rejected. A browser
may itself mix tabs into a single stream, so tab isolation is not guaranteed.
Recognition sends fingerprints to Shazam. Captured audio is not retained; full-track analysis temporarily downloads audio as described below.

Optional Spanish-readable pronunciation uses local eSpeak NG dictionaries and
Japanese romanization. Original and dual views preserve lyric timing. No lyric
text or audio is sent to a pronunciation service. The reading is approximate;
unsupported languages retain their original text.

Edited SoundCloud titles are normalized and searched in both artist/title orders.
The panel can use a persistent Whisper.cpp large-v3-turbo Vulkan service, tested
on RX590, or explicitly selected CrisperWhisper 2.0 CPU. DTW estimates phrase times;
three consistent unique anchors estimate a complete constant-speed lyric clock.
[Automatic timing and measured limits](docs/AUTOMATIC_TIMING.md) describes setup,
line start/end ranges, duration clipping, replay history and saved corrections. See [Whisper setup and
measured limits](docs/CRISPERWHISPER.md). Real catalog tests covered five SoundCloud
variants; automatic timing on arbitrary remixes is not guaranteed.

Full-track analysis is available in **⋯ → Analizar pista completa desde enlace**. It downloads the exact public upload, checks decoded duration, analyzes the entire timeline locally and removes temporary audio. Up to 16 transcripts remain in the local cache. [Usage, real tests and limits](docs/FULL_TRACK.md).

Latest validation and environment limitations are in [HANDOFF.md](HANDOFF.md).
See [Spanish usage](README.es.md).

![Current native panel, idle](docs/dashboard-preview.png)

## Initial prototype

Browser music → synchronized desktop lyrics, by connecting existing projects.

**Early integration prototype for Linux/KDE.** SoundCloud, Spotify Web and YouTube
are handled by the existing WebNowPlaying extension. Kotonoha handles the entire
lyrics overlay, search, cache and karaoke rendering. SingLayer is the small bridge
between them. That original mode does not download music or replace your player. The current panel also provides optional full-track analysis.

[Español](README.es.md) · [Upstream licenses](THIRD_PARTY.md) · [Validation](docs/VALIDATION.md)

![Actual Kotonoha renderer with the SingLayer preset and original demo text](docs/overlay-preview.png)

This is an actual render from the upstream widget, not a design mockup. The demo
text is original. Transparent background, cyan/lilac highlight, subtle glow and
previous/current/next lines are configured using upstream settings.

```text
SoundCloud / Spotify Web / YouTube in a browser
                       │
                WebNowPlaying extension
                       │ WebSocket, loopback port 8975
                 SingLayer bridge
                       │ MPRIS session bus
                 Kotonoha overlay
                       │
              LRCLIB / NetEase / Kugou
```

## What works, and what is still pending

| Capability | Status |
|---|---|
| Browser metadata, position, pause and track changes → MPRIS | Implemented; tested with protocol fixtures and real D-Bus |
| Multiple browser connections with overlapping player IDs | Implemented; most recently started playing source wins |
| Play/pause/seek/next/previous controls | Forwarded to the extension; browser acknowledgement required |
| Lyrics lookup, manual lyric search, per-track timing adjustment | Reused unchanged from Kotonoha |
| Three-line overlay, glow, word highlighting and click-through | Reused unchanged from Kotonoha; word timing requires a matching provider |
| X11 / Wayland native rendering | X11 smoke passed; isolated KWin Wayland render and native lifecycle test passed |
| Real SoundCloud/Spotify/YouTube session in Brave/Vivaldi | **Not yet verified**; requires installing/enabling the extension |
| Automatic SongRec fallback and recognition timeline alignment | **Not implemented**; upstream source is pinned for the next integration |
| Upcoming song/video or queue prefetch | **Not implemented**; WNP exposes next-track control, not queue identity |
| Click a lyric to mark “I am here” | **Not implemented**; upstream earlier/later timing controls are available |
| Speed changes, ads and remixes | Need site-specific validation; bridge assumes 1× playback |

## Install the prototype

Requirements: Linux desktop with a session D-Bus, Python 3.11+, Git, `uv`, CMake,
a C/C++ toolchain, system PyQt6, Qt6 base/private headers, Qt6 Wayland,
LayerShellQt development files and Wayland development tools. Use matching system
Qt/PyQt6: the native bridge depends on the Qt minor version. Arch/KDE is the
environment used for the initial build; other distributions are not yet tested.

On Arch, the relevant system packages are:

```sh
sudo pacman -S --needed python-pyqt6 qt6-base qt6-wayland layer-shell-qt wayland cmake base-devel git uv
```

For other distributions, use [Kotonoha's dependency instructions](https://github.com/locez/kotonoha#installation)
plus the distribution's PyQt6 package (`python3-pyqt6` on Debian/Ubuntu).

```sh
git clone https://github.com/Solar2004/SingLayer.git
cd SingLayer
bash scripts/setup.sh
```

Setup creates a local `.venv` using system PyQt6, installs pinned Python runtime
dependencies and builds the pinned Kotonoha checkout. It does not use sudo, edit
your browser profile, register autostart, or replace existing Kotonoha settings.
Run it again after upgrading system Qt. `SINGLAYER_PYTHON=/path/to/python3` can
select a different system Python with matching PyQt6 installed.

### Connect your browser

1. Install the official [WebNowPlaying extension](https://chromewebstore.google.com/detail/webnowplaying/jfakgfcdgpghbbefmdfjkbdlibjgnbli)
   in Brave, Vivaldi or Chrome, or use its [Firefox build](https://wnp.keifufu.dev/extension/getting-started).
2. In WebNowPlaying settings, add a **custom adapter** on port **8975**, and enable it.
   Disable **Use desktop players** for this adapter workflow to avoid feeding our
   own MPRIS player back into the extension. Browser sources are sufficient.
3. Run:

   ```sh
   .venv/bin/singlayer start
   ```

4. Play a song. Kotonoha's tray icon opens settings. Its magnifier searches for a
   different lyric match; earlier/later buttons adjust timing; lock enables
   click-through. Ctrl+C in the launch terminal stops both child processes.

The extension advertises these sites, but this prototype has not yet been tested
against live sessions on all three. Brave/Vivaldi permissions or site changes can
affect detection. `curl http://127.0.0.1:8975/health` shows connected browser/player
counts without exposing track names.

Default overlay settings are isolated under `$XDG_CONFIG_HOME/singlayer/kotonoha`
(normally `~/.config/singlayer/kotonoha`). Existing settings are preserved.
The initial preset follows `org.mpris.MediaPlayer2.singlayer`. Spotify desktop is
a separate MPRIS player; select it in Kotonoha's settings to follow it directly.

## SongRec and reuse boundaries

`singlayer recognize` opens an already-installed SongRec without starting capture.
It is currently a convenience launcher, **not an automatic recognition bridge**.
SongRec's MPRIS implementation publishes song identity but does not provide the
reliable playback position needed by this karaoke path. A future integration must
combine recognition metadata with a verified clock/offset, especially for DJ mixes.

All four researched repositories are pinned as submodules:

```sh
git submodule update --init  # also obtains optional SongRec and SyncLyrics references
```

SyncLyrics is not required or imported. Kotonoha already provides the needed UI
and lyric providers and has a permissive main license. See [THIRD_PARTY.md](THIRD_PARTY.md)
for the different licenses; upstream authors retain their credits.

## Development and verification

```sh
uv pip install --python .venv/bin/python pytest pytest-asyncio ruff
dbus-run-session -- .venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts/preview.py
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/preview.py
```

The connector test suite uses original synthetic metadata, an actual WebSocket
connection and private D-Bus. If Kotonoha is installed, an additional test uses its
real MPRIS consumer. CI intentionally tests the connector independently; it is not
proof of browser support or compositor behavior.

## Next contributions

1. Validate live SoundCloud in Brave and Vivaldi, then Spotify Web and YouTube.
2. Connect SongRec audio recognition with explicit capture controls and timeline alignment.
3. Add optional per-site next-item readers; report “unknown” when autoplay is not determined.
4. Add source selection and a precise “I'm singing this line” action by extending
   upstream seams rather than replacing the renderer.

No listening starts on install. The bridge listens only on loopback and rejects
web-page origins; browser-extension origins and native local clients are allowed.
Lyrics providers receive track metadata during lookups. SongRec, when explicitly
used, sends audio fingerprints to Shazam. Check upstream provider terms before
redistributing content. No accounts, credentials or cached lyrics are in this repo.

SingLayer's original code is MIT. This project is not affiliated with the upstream
projects, SoundCloud, Spotify, YouTube or Shazam.
