# Install SingLayer 0.2.0

SingLayer is a Linux desktop application. The tested environment is Arch Linux/KDE with an RX 590. Other distributions require equivalent system packages; Windows/macOS and unattended server installations are not supported.

## System requirements

Python 3.11+ with system PyQt6 (including QtWebSockets), Git, uv, CMake, a C++ compiler, pkg-config, FFmpeg and PulseAudio-compatible tools (`pactl`, `parec`). The native overlay additionally requires matching Qt6 development/private headers, Qt6 Wayland, LayerShellQt development files and Wayland development tools. Whisper GPU requires a working Vulkan driver, Vulkan/SPIR-V development headers, `glslc`, curl, sha256sum and ripgrep. Installation does not run sudo.

Arch example (review for your system):

```sh
sudo pacman -S --needed python-pyqt6 qt6-base qt6-websockets qt6-wayland layer-shell-qt wayland cmake base-devel git uv ffmpeg libpulse curl ripgrep vulkan-headers vulkan-devel shaderc spirv-headers
```

Install the appropriate Vulkan driver for your GPU using your distribution's documentation. See [Kotonoha dependencies](https://github.com/locez/kotonoha#installation) for other distributions. `SINGLAYER_PYTHON` can select a system Python whose PyQt6 matches system Qt.

## Download, review and run

```sh
curl -fL --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Solar2004/SingLayer/v0.2.0/scripts/install.sh -o /tmp/singlayer-install.sh
bash /tmp/singlayer-install.sh --check --with-whisper
bash /tmp/singlayer-install.sh --with-whisper
```

Or, after reviewing the script, the one-command form:

```sh
curl -fsSL --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Solar2004/SingLayer/v0.2.0/scripts/install.sh | bash -s -- --with-whisper
```

The installer checks executables and Python before cloning the fixed release. Native build dependencies are checked by the build. The default location is `~/.local/share/singlayer/app`; `--prefix /absolute/directory` chooses another location. Existing directories and shortcuts are preserved rather than overwritten. If a build fails, the directory remains available for inspection: fix the missing dependency and run its `scripts/setup.sh`, then `scripts/setup-whisper-vulkan.sh` if requested. The model download is approximately 574 MB; compilation needs additional disk space and time.

Without `--with-whisper`, the panel and catalogue integration are installed, but an acoustic transcription engine must be installed separately. The installer does not install CrisperWhisper model weights. Their separate licence and setup are described in [CRISPERWHISPER.md](CRISPERWHISPER.md).

Open **SingLayer** from the application menu. `~/.local/bin/singlayer app` also works when that directory is in PATH. The installer does not launch the application, enable autostart or modify browser profiles.

## Browser connection (required once)

1. Install [WebNowPlaying](https://wnp.keifufu.dev/extension/getting-started) in your browser. Enable a custom adapter on port **8975**; disable **Use desktop players** to avoid feeding SingLayer back into itself.
2. Load the companion extension from `~/.local/share/singlayer/source-link` using your browser's extension developer mode, then reload the music tab. This enables automatic exact-version analysis on SoundCloud/YouTube. Browser security requires this manual step.
3. Play music and open **⋯**. Choose **Whisper multilingüe · GPU Vulkan** and **Solo transcripción del audio** to use the audio transcript. Automatic mode combines catalogue and acoustic timing when evidence is consistent.

Whisper detects the language automatically, including Russian, Spanish, English, French and Japanese. It keeps the original language. You can enable Spanish-readable pronunciation independently. A multilingual model is not a guarantee of accurate lyrics: singing, instrumentals, heavy effects and changing languages can still cause errors. Russian is supported by the model, but this release's real-song timing benchmarks covered English, Japanese and French, not Russian. [Official model documentation](https://github.com/openai/whisper).

## Updating and removal

For a development checkout, preserve your local changes before updating, then run `git pull --ff-only`, `bash scripts/setup.sh` and, for the GPU engine, `bash scripts/setup-whisper-vulkan.sh`. Close your own application before updating. Tagged installations are fixed releases; install a future release into a different prefix rather than overwriting it.

To remove a user-local installation, close SingLayer and remove only its installation directory and shortcuts (`~/.local/bin/singlayer`, `~/.local/share/applications/singlayer.desktop`) if they belong to this installation. Preferences and transcript caches are retained unless you deliberately remove `~/.config/SingLayer`, `~/.config/singlayer` and `~/.cache/singlayer`.
