from __future__ import annotations

import time
from dataclasses import dataclass

from .audio import AudioRecorder
from .config import AppConfig
from .gemini import GeminiClient
from .x11_insert import type_text


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    duration_seconds: float
    started_at: float
    finished_at: float


class STTService:
    def __init__(self, config: AppConfig, api_key: str) -> None:
        self.config = config
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
        )
        self.client = GeminiClient(api_key=api_key, model=self.config.model)

    def transcribe_bytes(self, wav_bytes: bytes, duration_seconds: float = 0.0) -> TranscriptionResult:
        started = time.time()
        text = self.client.transcribe_wav(wav_bytes, prompt=self.config.prompt)
        finished = time.time()
        return TranscriptionResult(
            text=text,
            duration_seconds=duration_seconds,
            started_at=started,
            finished_at=finished,
        )

    def insert_text(self, text: str) -> None:
        type_text(text)
