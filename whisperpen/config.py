from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency
    yaml = None
    YAML_IMPORT_ERROR = exc
else:
    YAML_IMPORT_ERROR = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass(slots=True)
class RefineConfig:
    enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    prompt: str = (
        "修正語音辨識結果。保留技術名詞英文原文，去掉口語贅詞（嗯、那個、就是、然後），"
        "輸出繁體中文。只輸出修正後的文字，不要解釋。"
    )


@dataclass(slots=True)
class AudioConfig:
    sample_rate: int = 16_000
    channels: int = 1
    device: str | int | None = None
    subtype: str = "PCM_16"


@dataclass(slots=True)
class AppConfig:
    hotkey: str = "alt+a"
    model_path: str = ""
    model_size: str = "large-v3-turbo"
    language: str = "zh"
    initial_prompt: str = "繁體中文，technical terms 用英文。"
    beam_size: int = 5
    vad_filter: bool = True
    auto_paste: bool = True
    paste_keys: list[str] = field(default_factory=lambda: ["shift", "insert"])
    audio: AudioConfig = field(default_factory=AudioConfig)
    refine: RefineConfig = field(default_factory=RefineConfig)


DEFAULT_APP_CONFIG = AppConfig()
DEFAULT_AUDIO_CONFIG = AudioConfig()
DEFAULT_REFINE_CONFIG = RefineConfig()


def resolve_config_path(path: str | os.PathLike[str] | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()

    env_path = os.environ.get("WHISPERPEN_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()

    return DEFAULT_CONFIG_PATH


def load_config(path: str | os.PathLike[str] | None = None) -> tuple[Path, AppConfig]:
    config_path = resolve_config_path(path)

    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to load config.yaml. Install dependencies from requirements.txt."
        ) from YAML_IMPORT_ERROR

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    audio_raw = raw.get("audio", {}) or {}
    refine_raw = raw.get("refine", {}) or {}

    config = AppConfig(
        hotkey=raw.get("hotkey", DEFAULT_APP_CONFIG.hotkey),
        model_path=raw.get("model_path", DEFAULT_APP_CONFIG.model_path),
        model_size=raw.get("model_size", DEFAULT_APP_CONFIG.model_size),
        language=raw.get("language", DEFAULT_APP_CONFIG.language),
        initial_prompt=raw.get("initial_prompt", DEFAULT_APP_CONFIG.initial_prompt),
        beam_size=int(raw.get("beam_size", DEFAULT_APP_CONFIG.beam_size)),
        vad_filter=bool(raw.get("vad_filter", DEFAULT_APP_CONFIG.vad_filter)),
        auto_paste=bool(raw.get("auto_paste", DEFAULT_APP_CONFIG.auto_paste)),
        paste_keys=raw.get("paste_keys", DEFAULT_APP_CONFIG.paste_keys),
        audio=AudioConfig(
            sample_rate=int(audio_raw.get("sample_rate", DEFAULT_AUDIO_CONFIG.sample_rate)),
            channels=int(audio_raw.get("channels", DEFAULT_AUDIO_CONFIG.channels)),
            device=audio_raw.get("device", DEFAULT_AUDIO_CONFIG.device),
            subtype=audio_raw.get("subtype", DEFAULT_AUDIO_CONFIG.subtype),
        ),
        refine=RefineConfig(
            enabled=bool(refine_raw.get("enabled", DEFAULT_REFINE_CONFIG.enabled)),
            ollama_url=refine_raw.get("ollama_url", DEFAULT_REFINE_CONFIG.ollama_url),
            model=refine_raw.get("model", DEFAULT_REFINE_CONFIG.model),
            prompt=refine_raw.get("prompt", DEFAULT_REFINE_CONFIG.prompt),
        ),
    )
    return config_path, config


def config_signature(config: AppConfig) -> tuple[Any, ...]:
    return (
        config.model_path,
        config.model_size,
        config.language,
        config.initial_prompt,
        config.beam_size,
        config.vad_filter,
        config.audio.sample_rate,
        config.audio.channels,
        config.audio.device,
        config.audio.subtype,
    )
