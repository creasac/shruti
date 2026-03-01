from __future__ import annotations

import shutil
import subprocess


class InsertError(RuntimeError):
    """Raised when inserting text into X11 fails."""


def ensure_xdotool() -> None:
    if shutil.which("xdotool") is None:
        raise InsertError("xdotool is not installed. Install xdotool to use typing insertion.")


def type_text(text: str) -> None:
    ensure_xdotool()
    if not text:
        return
    try:
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "1", text],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InsertError(f"xdotool failed with exit code {exc.returncode}") from exc

