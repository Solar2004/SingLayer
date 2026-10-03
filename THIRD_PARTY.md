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
