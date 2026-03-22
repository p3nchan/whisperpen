from __future__ import annotations

import os
import tempfile
import threading
import wave
from pathlib import Path

try:
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover - runtime dependency
    sd = None
    SOUNDDEVICE_IMPORT_ERROR = exc
else:
    SOUNDDEVICE_IMPORT_ERROR = None


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16_000,
        channels: int = 1,
        device: str | int | None = None,
        subtype: str = "PCM_16",
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.subtype = subtype
        self._lock = threading.Lock()
        self._stream = None
        self._frames = bytearray()
        self._recording = False
        self._last_status: str | None = None

    def start(self) -> None:
        if sd is None:
            raise RuntimeError(
                "sounddevice is required for microphone capture. Install requirements.txt first."
            ) from SOUNDDEVICE_IMPORT_ERROR

        with self._lock:
            if self._recording:
                raise RuntimeError("Recorder is already running.")

            self._frames = bytearray()
            self._last_status = None
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device,
                callback=self._on_audio,
            )
            self._stream.start()
            self._recording = True

    def stop(self) -> Path:
        with self._lock:
            if not self._recording or self._stream is None:
                raise RuntimeError("Recorder is not running.")

            stream = self._stream
            self._stream = None
            self._recording = False

        stream.stop()
        stream.close()

        if not self._frames:
            raise RuntimeError("No audio captured. Check microphone permissions or input device.")

        fd, temp_name = tempfile.mkstemp(prefix="whisper-input-", suffix=".wav")
        os.close(fd)
        Path(temp_name).unlink(missing_ok=True)

        with wave.open(temp_name, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(bytes(self._frames))

        return Path(temp_name)

    def cancel(self) -> None:
        with self._lock:
            if not self._recording or self._stream is None:
                return
            stream = self._stream
            self._stream = None
            self._recording = False

        stream.stop()
        stream.close()
        self._frames = bytearray()

    def _on_audio(self, indata: bytes, frames: int, time_info, status) -> None:
        del frames, time_info
        if status:
            self._last_status = str(status)
        self._frames.extend(indata)
