from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayMessage:
    text: str
    level: float | None = None
    sticky: bool = False


class Overlay:
    def __init__(self) -> None:
        self._messages: queue.Queue[OverlayMessage] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        time.sleep(0.1)

    def show(self, text: str, level: float | None = None, sticky: bool = False) -> None:
        self._messages.put(OverlayMessage(text=text, level=level, sticky=sticky))

    def _run(self) -> None:
        root = tk.Tk()
        root.title("shruti")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="#111111")
        root.geometry("+40+40")

        frame = tk.Frame(root, bg="#111111", padx=14, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        status = tk.Label(
            frame,
            text="",
            fg="#f2f2f2",
            bg="#111111",
            font=("Sans", 12, "bold"),
        )
        status.pack(anchor="w")

        meter = tk.Label(
            frame,
            text="",
            fg="#6ee7b7",
            bg="#111111",
            font=("Monospace", 11),
        )
        meter.pack(anchor="w")

        hide_after_ms = 1000
        hide_job: str | None = None

        def set_message(msg: OverlayMessage) -> None:
            nonlocal hide_job
            status.config(text=msg.text)
            if msg.level is None:
                meter.config(text="")
            else:
                width = 20
                filled = max(0, min(width, int(msg.level * width)))
                meter.config(text=f"[{'#' * filled}{'.' * (width - filled)}]")
            root.deiconify()
            if hide_job:
                root.after_cancel(hide_job)
                hide_job = None
            if not msg.sticky:
                hide_job = root.after(hide_after_ms, root.withdraw)

        def pump() -> None:
            try:
                while True:
                    msg = self._messages.get_nowait()
                    set_message(msg)
            except queue.Empty:
                pass
            root.after(70, pump)

        root.withdraw()
        root.after(70, pump)
        root.mainloop()

