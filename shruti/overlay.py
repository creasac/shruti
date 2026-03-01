from __future__ import annotations

import threading
import time
import tkinter as tk
from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayMessage:
    kind: str = "recording"
    sticky: bool = False
    bars: tuple[float, ...] | None = None


class Overlay:
    def __init__(self) -> None:
        self._latest_message: OverlayMessage | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        time.sleep(0.1)

    def show(
        self,
        *,
        kind: str = "recording",
        sticky: bool = False,
        bars: list[float] | tuple[float, ...] | None = None,
    ) -> None:
        payload: tuple[float, ...] | None = None
        if bars is not None:
            payload = tuple(max(0.0, min(1.0, float(v))) for v in bars)
        with self._lock:
            self._latest_message = OverlayMessage(kind=kind, sticky=sticky, bars=payload)

    def _take_latest_message(self) -> OverlayMessage | None:
        with self._lock:
            msg = self._latest_message
            self._latest_message = None
            return msg

    def _run(self) -> None:
        width = 460
        height = 96

        x_pad = 22
        wave_top = 16
        wave_bottom = 56
        wave_mid = (wave_top + wave_bottom) / 2.0

        bar_count = 56
        span = width - (2 * x_pad)
        bar_step = span / float(bar_count)

        root = tk.Tk()
        root.title("shruti")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="#f6f2e8")
        root.attributes("-alpha", 0.98)

        canvas = tk.Canvas(root, width=width, height=height, bg="#f6f2e8", bd=0, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        def rounded_rect(x0: float, y0: float, x1: float, y1: float, radius: float, **kwargs: object) -> int:
            points = [
                x0 + radius,
                y0,
                x1 - radius,
                y0,
                x1,
                y0,
                x1,
                y0 + radius,
                x1,
                y1 - radius,
                x1,
                y1,
                x1 - radius,
                y1,
                x0 + radius,
                y1,
                x0,
                y1,
                x0,
                y1 - radius,
                x0,
                y0 + radius,
                x0,
                y0,
            ]
            return canvas.create_polygon(points, smooth=True, **kwargs)

        corner_radius = (height - 6) / 2.0
        panel = rounded_rect(
            2,
            2,
            width - 2,
            height - 2,
            corner_radius,
            fill="#faf7ef",
            outline="#d9d1bf",
            width=1.3,
        )
        baseline = canvas.create_line(x_pad, wave_mid, width - x_pad, wave_mid, fill="#d7cfbc", width=1)

        bars: list[int] = []
        for i in range(bar_count):
            x = x_pad + (i + 0.5) * bar_step
            bar = canvas.create_line(
                x,
                wave_mid,
                x,
                wave_mid,
                fill="#111827",
                width=2,
                capstyle=tk.ROUND,
            )
            bars.append(bar)

        label = canvas.create_text(
            width / 2,
            76,
            text="",
            fill="#5f6774",
            font=("Sans", 9),
        )

        styles: dict[str, dict[str, str]] = {
            "recording": {
                "panel": "#faf7ef",
                "outline": "#d9d1bf",
                "mid": "#d7cfbc",
                "wave": "#111827",
                "text": "#525a67",
            },
            "transcribing": {
                "panel": "#f3f7fc",
                "outline": "#c7d3e4",
                "mid": "#ced8e8",
                "wave": "#1f3b6f",
                "text": "#3a5888",
            },
            "done": {
                "panel": "#edf8ef",
                "outline": "#bfd8c2",
                "mid": "#d3e7d5",
                "wave": "#1f6b3a",
                "text": "#2f7b4b",
            },
            "cancelled": {
                "panel": "#fff5ea",
                "outline": "#e3c9a8",
                "mid": "#ebd9bf",
                "wave": "#9a5a1f",
                "text": "#995f28",
            },
            "error": {
                "panel": "#fff0f2",
                "outline": "#e7bec7",
                "mid": "#efc9d1",
                "wave": "#8a2a3b",
                "text": "#9a3448",
            },
            "info": {
                "panel": "#faf7ef",
                "outline": "#d9d1bf",
                "mid": "#d7cfbc",
                "wave": "#111827",
                "text": "#5f6774",
            },
        }

        hide_job: str | None = None
        bar_heights = [1.0 for _ in range(bar_count)]
        state = {
            "kind": "info",
            "bars": tuple(0.0 for _ in range(bar_count)),
            "gain": 4.0,
        }

        def place_top_center() -> None:
            root.update_idletasks()
            x = max(0, (root.winfo_screenwidth() - width) // 2)
            root.geometry(f"{width}x{height}+{x}+24")

        def auto_hide_ms(kind: str) -> int:
            if kind in {"done", "cancelled"}:
                return 850
            if kind == "error":
                return 1800
            return 1100

        def action_text(kind: str) -> str:
            if kind == "recording":
                return "recording"
            if kind == "transcribing":
                return "transcribing"
            return ""

        def current_style() -> dict[str, str]:
            return styles.get(str(state["kind"]), styles["info"])

        def apply_style() -> None:
            s = current_style()
            canvas.itemconfigure(panel, fill=s["panel"], outline=s["outline"])
            canvas.itemconfigure(baseline, fill=s["mid"])
            canvas.itemconfigure(label, fill=s["text"], text=action_text(str(state["kind"])))

        def _resample(values: tuple[float, ...], target_count: int) -> list[float]:
            source_count = len(values)
            if source_count == 0:
                return [0.0] * target_count
            if source_count == target_count:
                return list(values)
            if source_count == 1:
                return [float(values[0])] * target_count

            out: list[float] = []
            last = source_count - 1
            for i in range(target_count):
                pos = (i * last) / float(target_count - 1)
                left = int(pos)
                right = min(last, left + 1)
                blend = pos - left
                value = (1.0 - blend) * float(values[left]) + blend * float(values[right])
                out.append(value)
            return out

        def draw_bars(values: tuple[float, ...], gain_scale: float = 1.0) -> None:
            normalized = _resample(values, bar_count)
            peak = max(normalized) if normalized else 0.0
            target_gain = 2.0
            if peak > 0.0005:
                target_gain = min(14.0, max(2.0, 0.82 / peak))

            current_gain = float(state["gain"])
            current_gain = (current_gain * 0.84) + (target_gain * 0.16)
            state["gain"] = current_gain

            half_height = (wave_bottom - wave_top) / 2.0 - 1.0
            min_height = 1.2
            for i, bar in enumerate(bars):
                value = max(0.0, min(1.0, normalized[i]))
                target = min(half_height, max(min_height, value * current_gain * half_height * gain_scale))

                prev = bar_heights[i]
                if target >= prev:
                    height_now = (prev * 0.40) + (target * 0.60)
                else:
                    height_now = (prev * 0.82) + (target * 0.18)
                bar_heights[i] = height_now

                x = x_pad + (i + 0.5) * bar_step
                y0 = wave_mid - height_now
                y1 = wave_mid + height_now
                canvas.coords(bar, x, y0, x, y1)
                canvas.itemconfigure(bar, fill=current_style()["wave"])

        def set_message(msg: OverlayMessage) -> None:
            nonlocal hide_job
            state["kind"] = msg.kind
            if msg.bars is not None:
                state["bars"] = msg.bars

            apply_style()
            root.deiconify()
            root.lift()

            if hide_job:
                root.after_cancel(hide_job)
                hide_job = None
            if not msg.sticky:
                hide_job = root.after(auto_hide_ms(msg.kind), root.withdraw)

        def pump() -> None:
            msg = self._take_latest_message()
            if msg is not None:
                set_message(msg)

            if root.state() != "withdrawn":
                kind = str(state["kind"])
                bars_data = state["bars"]
                if kind == "transcribing":
                    draw_bars(bars_data, gain_scale=0.85)
                elif kind == "recording":
                    draw_bars(bars_data, gain_scale=1.0)
                else:
                    draw_bars(tuple(0.0 for _ in range(bar_count)), gain_scale=0.7)

            root.after(42, pump)

        root.withdraw()
        place_top_center()
        root.after(42, pump)
        root.mainloop()
