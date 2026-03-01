from __future__ import annotations

from collections import deque
import io
import threading
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
        self._recent_chunks: deque[np.ndarray] = deque()
        self._recent_samples = 0
        self._max_recent_samples = int(self.sample_rate * 0.6)
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def is_recording(self) -> bool:
        return self._stream is not None

    def waveform_bars(self, bars: int = 56) -> list[float]:
        with self._lock:
            if not self._recent_chunks:
                return [0.0] * bars
            samples = np.concatenate(list(self._recent_chunks), axis=0)

        if samples.size == 0:
            return [0.0] * bars

        amplitude = np.abs(samples.astype(np.float32) / 32768.0)
        count = max(8, bars)
        edges = np.linspace(0, amplitude.size, num=count + 1, dtype=np.int64)

        out = np.zeros(count, dtype=np.float32)
        for i in range(count):
            start = int(edges[i])
            end = int(edges[i + 1])
            if end <= start:
                out[i] = 0.0
                continue
            segment = amplitude[start:end]
            out[i] = float(np.percentile(segment, 90.0))

        curved = np.power(np.clip(out, 0.0, 1.0), 0.65)
        return curved.tolist()

    def _callback(self, indata: np.ndarray, _frames: int, _time: object, _status: object) -> None:
        with self._lock:
            copy = indata.copy()
            self._frames.append(copy)
            mono = copy[:, 0] if copy.ndim == 2 else copy
            mono_chunk = np.ascontiguousarray(mono.reshape(-1))
            self._recent_chunks.append(mono_chunk)
            self._recent_samples += int(mono_chunk.size)
            while self._recent_samples > self._max_recent_samples and self._recent_chunks:
                dropped = self._recent_chunks.popleft()
                self._recent_samples -= int(dropped.size)

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Recorder is already running.")
        with self._lock:
            self._frames = []
            self._recent_chunks.clear()
            self._recent_samples = 0
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
            self._recent_chunks.clear()
            self._recent_samples = 0

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
