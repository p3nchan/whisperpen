from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

try:
    import keyboard
except ImportError as exc:  # pragma: no cover - runtime dependency
    keyboard = None
    KEYBOARD_IMPORT_ERROR = exc
else:
    KEYBOARD_IMPORT_ERROR = None

try:
    import pystray
    from pystray import MenuItem as Item
except ImportError as exc:  # pragma: no cover - runtime dependency
    pystray = None
    Item = None
    PYSTRAY_IMPORT_ERROR = exc
else:
    PYSTRAY_IMPORT_ERROR = None

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - runtime dependency
    Image = None
    ImageDraw = None
    PIL_IMPORT_ERROR = exc
else:
    PIL_IMPORT_ERROR = None

from config import AppConfig, config_signature, load_config
from paster import copy_text, paste_text
from recorder import AudioRecorder
from refiner import refine_text
from transcriber import WhisperTranscriber


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("whisper-tray")


class TrayApplication:
    def __init__(self) -> None:
        self.config_path, self.config = load_config()
        self._config_signature = config_signature(self.config)
        self._config_mtime = self._read_config_mtime()
        self._refine_override: bool | None = None
        self._recording = False
        self._processing = False
        self._shutdown = False
        self._state_lock = threading.Lock()
        self._keyboard_hook = None

        self.recorder = self._build_recorder(self.config)
        self.transcriber = WhisperTranscriber(self.config)

        self.icon = self._build_icon()
        self._set_icon(recording=False)

    def run(self) -> None:
        self._install_keyboard_hook()
        self._preload_model()
        self._notify("Whisper tray app started", title="Whisper")
        self.icon.run()

    def _build_recorder(self, config: AppConfig) -> AudioRecorder:
        return AudioRecorder(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            device=config.audio.device,
            subtype=config.audio.subtype,
        )

    def _build_icon(self):
        if pystray is None:
            raise RuntimeError(
                "pystray is required for the tray icon. Install requirements.txt first."
            ) from PYSTRAY_IMPORT_ERROR
        if Image is None or ImageDraw is None:
            raise RuntimeError(
                "Pillow is required for tray icon rendering. Install requirements.txt first."
            ) from PIL_IMPORT_ERROR

        return pystray.Icon(
            "whisper-tray",
            title="Whisper Voice Input",
            menu=pystray.Menu(
                Item(
                    "Toggle LLM Refine",
                    self._toggle_refine,
                    checked=lambda item: self.refine_enabled,
                ),
                Item("Settings", self._open_settings),
                Item("Quit", self._quit),
            ),
        )

    @property
    def refine_enabled(self) -> bool:
        if self._refine_override is None:
            return self.config.refine.enabled
        return self._refine_override

    def _read_config_mtime(self) -> int | None:
        try:
            return self.config_path.stat().st_mtime_ns
        except OSError:
            return None

    def _reload_config_if_needed(self, force: bool = False) -> None:
        latest_mtime = self._read_config_mtime()
        if not force and latest_mtime == self._config_mtime:
            return

        config_path, config = load_config(self.config_path)
        signature = config_signature(config)
        if signature != self._config_signature:
            self.transcriber = WhisperTranscriber(config)
            self.recorder = self._build_recorder(config)
            self._config_signature = signature
        self.config_path = config_path
        self.config = config
        self._config_mtime = latest_mtime

    def _install_keyboard_hook(self) -> None:
        if keyboard is None:
            raise RuntimeError(
                "keyboard is required for global hotkeys. Install requirements.txt first."
            ) from KEYBOARD_IMPORT_ERROR

        keyboard.add_hotkey(self.config.hotkey, self._on_hotkey_toggle, suppress=False)
        LOGGER.info("Listening for hotkey (toggle mode): %s", self.config.hotkey)

    def _on_hotkey_toggle(self) -> None:
        if self._shutdown:
            return

        with self._state_lock:
            if self._processing:
                return
            if self._recording:
                self._recording = False
                self._set_icon(recording=False)
                do_stop = True
            else:
                do_stop = False

        if do_stop:
            self._handle_hotkey_release()
        else:
            self._handle_hotkey_press()

    def _handle_hotkey_press(self) -> None:
        try:
            with self._state_lock:
                if self._recording or self._processing:
                    return
                self._reload_config_if_needed(force=True)
                self.recorder.start()
                self._recording = True
                self._set_icon(recording=True)
        except Exception as exc:
            with self._state_lock:
                self._recording = False
            LOGGER.exception("Failed to start recording.")
            self._notify(f"Recording failed: {exc}", title="Whisper")
            return

        LOGGER.info("Recording started.")
        self._notify("Recording...", title="Whisper")

    def _handle_hotkey_release(self) -> None:
        with self._state_lock:
            self._processing = True

        try:
            audio_path = self.recorder.stop()
        except Exception as exc:
            with self._state_lock:
                self._processing = False
            LOGGER.exception("Failed to stop recorder.")
            self._notify(f"Recording failed: {exc}", title="Whisper")
            return

        worker = threading.Thread(
            target=self._process_audio,
            args=(audio_path,),
            name="whisper-process",
            daemon=True,
        )
        worker.start()

    def _process_audio(self, audio_path: Path) -> None:
        try:
            LOGGER.info("Transcribing %s", audio_path)
            text = self.transcriber.transcribe(audio_path)
            if self.refine_enabled:
                try:
                    text = refine_text(text, self.config.refine)
                except Exception:
                    LOGGER.exception("Refine failed. Falling back to raw transcript.")
            if self.config.auto_paste:
                paste_text(text, auto_paste=True, paste_keys=self.config.paste_keys)
            else:
                copy_text(text)
            preview = text if len(text) <= 50 else f"{text[:47]}..."
            self._notify(f"Pasted: {preview}", title="Whisper")
        except Exception as exc:
            LOGGER.exception("Audio pipeline failed.")
            self._notify(f"Transcription failed: {exc}", title="Whisper")
        finally:
            audio_path.unlink(missing_ok=True)
            with self._state_lock:
                self._processing = False

    def _toggle_refine(self, _icon, _item) -> None:
        self._refine_override = not self.refine_enabled
        state = "on" if self.refine_enabled else "off"
        self._notify(f"LLM refine {state}", title="Whisper")

    def _open_settings(self, _icon, _item) -> None:
        self._open_path(self.config_path)

    def _quit(self, _icon, _item) -> None:
        self._shutdown = True
        try:
            self.recorder.cancel()
        except Exception:
            LOGGER.exception("Failed to cancel recorder during shutdown.")
        if keyboard is not None and self._keyboard_hook is not None:
            keyboard.unhook(self._keyboard_hook)
        self.icon.stop()

    def _preload_model(self) -> None:
        worker = threading.Thread(
            target=self._preload_model_worker,
            name="whisper-preload",
            daemon=True,
        )
        worker.start()

    def _preload_model_worker(self) -> None:
        try:
            self.transcriber.ensure_model_loaded()
            LOGGER.info("Model preloaded.")
        except Exception:
            LOGGER.exception("Model preload failed.")

    def _notify(self, message: str, title: str) -> None:
        LOGGER.info("%s: %s", title, message)
        try:
            self.icon.notify(message, title=title)
        except Exception:
            return

    def _set_icon(self, recording: bool) -> None:
        color = "#d64545" if recording else "#777777"
        self.icon.icon = self._make_microphone_icon(color)

    def _make_microphone_icon(self, color: str):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rounded_rectangle((24, 10, 40, 34), radius=8, fill=color)
        draw.rectangle((29, 32, 35, 46), fill=color)
        draw.arc((18, 18, 46, 46), start=200, end=-20, fill=color, width=4)
        draw.rounded_rectangle((22, 46, 42, 52), radius=3, fill=color)
        return image

    def _open_path(self, path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return

        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
            return

        subprocess.run(["xdg-open", str(path)], check=False)


if __name__ == "__main__":
    app = TrayApplication()
    app.run()
