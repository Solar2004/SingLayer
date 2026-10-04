# SingLayer

[![Tests](https://github.com/Solar2004/SingLayer/actions/workflows/test.yml/badge.svg)](https://github.com/Solar2004/SingLayer/actions/workflows/test.yml)

Synchronized desktop lyrics for browser music on Linux. A native panel connects WebNowPlaying, catalogue lookup, Shazam recognition and local multilingual audio transcription to the Kotonoha overlay.

[Español](README.es.md) · [Install](docs/INSTALL.md) · [Measured performance](docs/ENCODER_REUSE.md) · [Licences](THIRD_PARTY.md)

![Native SingLayer panel](docs/dashboard-preview.png)

## Install

Linux desktop, Python 3.11+, system Qt/PyQt6 and native build dependencies are required. Arch/KDE with RX 590 is the tested environment. Read the [dependency list and installation guide](docs/INSTALL.md) first.

```sh
curl -fsSL --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Solar2004/SingLayer/v0.2.0/scripts/install.sh | bash -s -- --with-whisper
```

The installer uses a fixed release and your user directory, preserves existing installations, creates an application shortcut and validates actual Vulkan inference. It requires internet and does not install system packages. Browser extensions require a one-time manual configuration.

## Use

1. Open **SingLayer** from your application menu.
2. Connect WebNowPlaying on port **8975**. Load the [source-link companion extension](docs/AUTOMATIC_SOURCE.md) for automatic SoundCloud/YouTube exact-version analysis.
3. Play a song. In **⋯**, choose the engine, catalogue/audio source and pronunciation view.

**Whisper multilingüe · GPU Vulkan** automatically detects languages, including Russian; it transcribes in the original language. **Solo transcripción del audio** chooses acoustic lyrics when the catalogue is unsuitable. CrisperWhisper CPU remains separately installable and explicitly selectable. Its model has a non-commercial licence.

## Behaviour and limits

- Catalogue results, recognition and acoustic evidence help identify the track and align its lyrics. Slowed/sped-up recordings and edits use measured audio timing; unsupported or inconsistent matches are not presented as confirmed synchronization.
- Exact public SoundCloud/YouTube uploads can be analyzed completely. Lyrics appear progressively near the playhead; up to16 completed transcripts are cached for24 hours. Downloaded audio is temporary.
- Local pronunciation guides preserve original lyrics and timing. They are approximate readings for Spanish speakers, not translations.
- Recognition sends fingerprints to Shazam. Catalogue lookup and downloads require network access; Whisper transcription and pronunciation run locally.

In a real RX590 test, a177-second SoundCloud track completed in102 seconds versus150 in the previous run, with first lyrics at16.75 seconds. Five identical-window comparisons preserved text/times while reducing inference time approximately29–32%. These are individual measurements, not guarantees. The complete runs produced42 and43 lines. [Evidence and limits](docs/ENCODER_REUSE.md).

Lyrics and times remain estimates. Instrumentals and processed vocals can cause ASR errors; remixes and cuts do not always follow a uniform clock. SoundCloud browser integration and full-track transcription have been exercised; YouTube full download was checked, while full-track YouTube ASR and Russian singing are not yet benchmarked. Spotify browser metadata is supported by WebNowPlaying, but automatic full-audio download is limited to the supported public sources.

## Development

```sh
git clone https://github.com/Solar2004/SingLayer.git
cd SingLayer
bash scripts/setup.sh
bash scripts/setup-whisper-vulkan.sh
.venv/bin/singlayer app
```

[Current handoff](HANDOFF.md) · [Progressive timing](docs/PROGRESSIVE_TIMING.md) · [Complete-track analysis](docs/FULL_TRACK.md) · [Pronunciation](src/singlayer/pronunciation/SKILL.md)

The legacy `singlayer start` command is retained for the earlier MPRIS integration; use `singlayer app` for the current panel.

SingLayer is MIT licensed. Upstream projects and model weights retain their own licences; review [THIRD_PARTY.md](THIRD_PARTY.md) before redistribution or commercial use.
