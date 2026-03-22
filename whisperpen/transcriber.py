from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


def _collect_nvidia_dll_dirs() -> list[str]:
    site_roots: list[Path] = []

    # Check WHISPERPEN_CUDA_PATH env var first
    env_path = os.environ.get("WHISPERPEN_CUDA_PATH")
    if env_path:
        site_roots.append(Path(env_path))

    # Auto-detect from current Python environment
    executable_site = Path(sys.executable).resolve().parent.parent / "Lib" / "site-packages"
    site_roots.append(executable_site)

    # Also check VIRTUAL_ENV if set
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        site_roots.append(Path(venv) / "Lib" / "site-packages")

    dll_dirs: list[str] = []
    seen: set[str] = set()
    for site_root in site_roots:
        for suffix in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cudnn/lib"):
            dll_dir = (site_root / suffix).resolve()
            if not dll_dir.is_dir():
                continue
            normalized = str(dll_dir)
            if normalized in seen:
                continue
            seen.add(normalized)
            dll_dirs.append(normalized)
    return dll_dirs


def _prime_windows_cuda_path() -> None:
    dll_dirs = _collect_nvidia_dll_dirs()
    if not dll_dirs:
        return

    os.environ["PATH"] = os.pathsep.join(dll_dirs) + os.pathsep + os.environ.get("PATH", "")
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is None:
        return

    for dll_dir in dll_dirs:
        try:
            add_dll_directory(dll_dir)
        except OSError:
            continue


_prime_windows_cuda_path()

try:
    from faster_whisper import WhisperModel
except ImportError as exc:  # pragma: no cover - runtime dependency
    WhisperModel = None
    FASTER_WHISPER_IMPORT_ERROR = exc
else:
    FASTER_WHISPER_IMPORT_ERROR = None

from config import AppConfig


class WhisperTranscriber:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._model = None

    def ensure_model_loaded(self) -> None:
        if WhisperModel is None:
            raise RuntimeError(
                "faster-whisper is required for transcription. Install requirements.txt first."
            ) from FASTER_WHISPER_IMPORT_ERROR

        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return

            self._model = WhisperModel(
                self.config.model_size,
                device="cuda",
                compute_type="float16",
                download_root=self.config.model_path,
            )

    def transcribe(self, audio_path: str | os.PathLike[str]) -> str:
        self.ensure_model_loaded()
        assert self._model is not None

        segments, _info = self._model.transcribe(
            str(audio_path),
            language=self.config.language,
            initial_prompt=self.config.initial_prompt,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
        )
        text = "".join(segment.text for segment in segments).strip()

        # Fallback: if VAD filtered everything out, retry without VAD
        if not text and self.config.vad_filter:
            import logging
            logging.getLogger("whisper-tray").info("VAD returned empty, retrying without VAD filter")
            segments, _info = self._model.transcribe(
                str(audio_path),
                language=self.config.language,
                initial_prompt=self.config.initial_prompt,
                beam_size=self.config.beam_size,
                vad_filter=False,
            )
            text = "".join(segment.text for segment in segments).strip()

        if not text:
            raise RuntimeError("Whisper returned empty text.")
        return _normalize_cjk_punctuation(text)


_HALFWIDTH_TO_FULLWIDTH = str.maketrans({
    ",": "，",
    "?": "？",
    "!": "！",
    ":": "：",
    ";": "；",
    "(": "（",
    ")": "）",
})


def _normalize_cjk_punctuation(text: str) -> str:
    """Convert half-width punctuation to full-width for CJK text."""
    return text.translate(_HALFWIDTH_TO_FULLWIDTH)

