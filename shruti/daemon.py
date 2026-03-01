from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from pynput import keyboard

from .overlay import Overlay
from .service import STTService


@dataclass(frozen=True)
class DaemonOptions:
    insert_text: bool = True


class STTDaemon:
    def __init__(self, service: STTService, options: DaemonOptions) -> None:
        self.service = service
        self.options = options
        self.overlay = Overlay()
        self._lock = threading.Lock()
        self._recording = False
        self._cancelled = False
        self._record_started_at = 0.0
        self._hotkeys: keyboard.GlobalHotKeys | None = None
        self._esc_listener: keyboard.Listener | None = None
        self._meter_thread: threading.Thread | None = None
        self._watchdog_thread: threading.Thread | None = None

    def _create_hotkeys(self) -> keyboard.GlobalHotKeys:
        hotkey = self.service.config.hotkey
        try:
            return keyboard.GlobalHotKeys({hotkey: self.toggle_recording})
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid hotkey '{hotkey}'. Use a format like "
                "'<ctrl>+<space>' or '<ctrl>+<alt>+h'."
            ) from exc

    def start(self) -> None:
        self._hotkeys = self._create_hotkeys()
        self.overlay.start()
        self._esc_listener = keyboard.Listener(on_press=self._on_press)
        self._hotkeys.start()
        self._esc_listener.start()
        self.overlay.show(f"shruti ready: {self.service.config.hotkey}", sticky=False)

        # Block forever, with Ctrl+C handled by caller.
        while True:
            time.sleep(0.2)

    def toggle_recording(self) -> None:
        with self._lock:
            if not self._recording:
                self._start_recording_locked()
            else:
                self._stop_recording_locked(cancel=False)

    def _on_press(self, key: keyboard.KeyCode | keyboard.Key | None) -> None:
        if key == keyboard.Key.esc:
            with self._lock:
                if self._recording:
                    self._stop_recording_locked(cancel=True)

    def _start_recording_locked(self) -> None:
        self.service.recorder.start()
        self._recording = True
        self._cancelled = False
        self._record_started_at = time.time()
        self.overlay.show("Recording... Press hotkey to stop, Esc to cancel.", level=0.0, sticky=True)

        self._meter_thread = threading.Thread(target=self._meter_loop, daemon=True)
        self._meter_thread.start()
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def _stop_recording_locked(self, cancel: bool) -> None:
        if not self._recording:
            return

        self._recording = False
        self._cancelled = cancel
        try:
            recording = self.service.recorder.stop()
        except Exception as exc:  # noqa: BLE001
            self.overlay.show(f"Recording failed: {exc}", sticky=False)
            return

        if cancel:
            self.overlay.show("Recording cancelled.", sticky=False)
            return

        self.overlay.show("Transcribing...", sticky=True)
        threading.Thread(
            target=self._transcribe_and_insert,
            args=(recording.data, recording.duration_seconds),
            daemon=True,
        ).start()

    def _meter_loop(self) -> None:
        while True:
            with self._lock:
                if not self._recording:
                    break
            self.overlay.show(
                "Recording... Press hotkey to stop, Esc to cancel.",
                level=self.service.recorder.level,
                sticky=True,
            )
            time.sleep(0.1)

    def _watchdog_loop(self) -> None:
        max_seconds = self.service.config.max_record_seconds
        while True:
            with self._lock:
                if not self._recording:
                    return
                elapsed = time.time() - self._record_started_at
                if elapsed >= max_seconds:
                    self._stop_recording_locked(cancel=False)
                    return
            time.sleep(0.25)

    def _transcribe_and_insert(self, wav_data: bytes, duration_seconds: float) -> None:
        try:
            result = self.service.transcribe_bytes(wav_data, duration_seconds=duration_seconds)
            if self.options.insert_text:
                self.service.insert_text(result.text)
            self.overlay.show("Done.", sticky=False)
        except Exception as exc:  # noqa: BLE001
            self.overlay.show(f"Transcription failed: {exc}", sticky=False)
