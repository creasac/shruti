from __future__ import annotations

import io
import threading
import time
import wave
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass(frozen=True)
class RecordingResult:
    data: bytes
    duration_seconds: float


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._started_at: float | None = None
        self._last_level = 0.0

    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def level(self) -> float:
        with self._lock:
            return self._last_level

    def _callback(self, indata: np.ndarray, _frames: int, _time: object, _status: object) -> None:
        with self._lock:
            copy = indata.copy()
            self._frames.append(copy)
            mono = copy[:, 0] if copy.ndim == 2 else copy
            rms = float(np.sqrt(np.mean(np.square(mono.astype(np.float32)))))
            self._last_level = min(1.0, rms / 32768.0)

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Recorder is already running.")
        with self._lock:
            self._frames = []
            self._last_level = 0.0
        self._started_at = time.time()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> RecordingResult:
        if self._stream is None:
            raise RuntimeError("Recorder is not running.")
        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()

        with self._lock:
            frames = self._frames
            self._frames = []
            self._last_level = 0.0

        if not frames:
            raise RuntimeError("No audio captured.")

        audio = np.concatenate(frames, axis=0)
        duration = len(audio) / float(self.sample_rate)
        wav = io.BytesIO()
        with wave.open(wav, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())
        return RecordingResult(data=wav.getvalue(), duration_seconds=duration)

