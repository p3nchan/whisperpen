<p align="center">
  <img src="assets/banner.svg" alt="WhisperPen" width="100%">
</p>

# WhisperPen

**Local voice-to-text for Windows.** Press a hotkey, speak, and your words appear as text — powered by your own GPU, no cloud needed.

WhisperPen runs [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on your NVIDIA GPU for real-time speech recognition, with optional LLM-powered text cleanup via [Ollama](https://ollama.com/).

> 📖 **中文介紹 →** [WhisperPen：用你的顯卡打造免費本地語音輸入](https://penchan.co/ai/20260322-whisperpen/)

## Features

- **Fully local** — your audio never leaves your machine
- **Fast** — under 1 second for short sentences on an RTX 3080
- **CJK-friendly** — handles Chinese-English mixed speech well, auto-converts half-width punctuation to full-width (，？！：；)
- **Toggle mode** — press hotkey once to start recording, again to stop (no need to hold)
- **System tray** — runs silently in the background, mic icon turns red when recording
- **LLM refine** — optional Ollama integration to remove filler words and fix recognition errors
- **Configurable** — hotkey, model, language, paste behavior, all via YAML config with hot-reload

## Requirements

- **Windows** 10/11
- **Python** 3.12+
- **NVIDIA GPU** with CUDA support (tested on RTX 3080, ~2GB VRAM for large-v3-turbo)
- **Ollama** (optional, for LLM text refinement)

## Quick Start

```bash
git clone https://github.com/pench4n/whisperpen.git
cd whisperpen
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python whisperpen/main.py
```

The first run downloads the Whisper model (~1.5GB). After that, WhisperPen starts in your system tray.

**Default hotkey: `Alt+A`** (toggle: press once to start, again to stop)

### Desktop Shortcut (optional)

Create `whisperpen.bat`:
```batch
@echo off
cd /d C:\path\to\whisperpen
call venv\Scripts\activate.bat
start /b pythonw whisperpen\main.py
exit
```

Right-click → Create Shortcut → move to Desktop. For auto-start, put the shortcut in `shell:startup`.

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit:

```yaml
hotkey: "alt+a"               # Toggle recording hotkey
model_size: "large-v3-turbo"  # Whisper model (see options below)
language: "zh"                # Primary language
auto_paste: true              # Auto-paste after transcription
paste_keys: ["ctrl", "v"]    # Paste shortcut to simulate

refine:
  enabled: false              # Enable Ollama text cleanup
  ollama_url: "http://localhost:11434"
  model: "qwen2.5:7b"
```

Changes are picked up automatically (hot-reload).

### Whisper Models

| Model | VRAM | Speed | Accuracy | Best for |
|-------|------|-------|----------|----------|
| `tiny` | ~1GB | fastest | fair | Quick drafts |
| `base` | ~1GB | fast | good | Casual use |
| `small` | ~2GB | moderate | good | Daily use |
| `large-v3-turbo` | ~2GB | fast | great | **Recommended** |
| `large-v3` | ~4GB | slower | best | Maximum accuracy |

### LLM Refinement

When `refine.enabled` is `true`, WhisperPen sends the raw transcript to a local Ollama model to:
- Remove filler words (嗯, 那個, 就是, 然後)
- Fix misheard technical terms
- Clean up formatting

You can toggle this on/off from the tray icon right-click menu.

## Troubleshooting

**CUDA DLL not found**: WhisperPen auto-detects NVIDIA DLLs from your Python environment. If it fails, set the environment variable:
```
set WHISPERPEN_CUDA_PATH=C:\path\to\venv\Lib\site-packages
```

**No audio captured**: Check your microphone. List devices with:
```bash
python -c "import sounddevice; print(sounddevice.query_devices())"
```
Then set `audio.device` in config.yaml to the correct device index.

**Ollama connection error**: Make sure Ollama is running (`ollama serve`) or set `refine.enabled: false`.

## Architecture

```
whisperpen/
  main.py          # Tray icon, hotkey listener, orchestration
  recorder.py      # Microphone capture via sounddevice
  transcriber.py   # faster-whisper GPU inference + CJK punctuation fix
  refiner.py       # Ollama API for text cleanup
  paster.py        # Clipboard + auto-paste
  config.py        # YAML config loader with hot-reload
```

## License

MIT
