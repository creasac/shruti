from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".config" / "shruti"
CONFIG_PATH = CONFIG_DIR / "config.toml"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.toml"

DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_MAX_RECORD_SECONDS = 300
DEFAULT_HOTKEY = "<ctrl>+<space>"
DEFAULT_PROMPT = (
    "Transcribe this audio exactly. Return only the transcript text. "
    "No summaries, no labels, no extra commentary."
)

# Accept common plain key names in config and normalize to pynput token format.
_SPECIAL_HOTKEY_TOKENS = {
    "alt",
    "alt_gr",
    "backspace",
    "caps_lock",
    "cmd",
    "ctrl",
    "delete",
    "down",
    "end",
    "enter",
    "esc",
    "home",
    "insert",
    "left",
    "num_lock",
    "page_down",
    "page_up",
    "pause",
    "print_screen",
    "right",
    "scroll_lock",
    "shift",
    "space",
    "super",
    "tab",
    "up",
    "windows",
}


@dataclass(frozen=True)
class AppConfig:
    model: str
    sample_rate: int
    channels: int
    max_record_seconds: int
    hotkey: str
    prompt: str


def _parse_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    return data if isinstance(data, dict) else {}


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _ensure_credentials_permissions() -> None:
    if not CREDENTIALS_PATH.exists():
        return
    mode = stat.S_IMODE(CREDENTIALS_PATH.stat().st_mode)
    if mode & 0o077:
        raise RuntimeError(
            f"Insecure permissions on {CREDENTIALS_PATH} ({oct(mode)}). "
            f"Run: chmod 600 {CREDENTIALS_PATH}"
        )


def normalize_hotkey(hotkey: str) -> str:
    tokens = [token.strip() for token in hotkey.split("+") if token.strip()]
    if not tokens:
        return DEFAULT_HOTKEY

    normalized: list[str] = []
    for token in tokens:
        if token.startswith("<") and token.endswith(">"):
            normalized.append(token.lower())
            continue

        lower = token.lower()
        if lower in _SPECIAL_HOTKEY_TOKENS:
            normalized.append(f"<{lower}>")
        else:
            normalized.append(token)

    return "+".join(normalized)


def _format_config_toml(config: AppConfig) -> str:
    return "\n".join(
        [
            "# shruti configuration",
            f"model = {_toml_string(config.model)}",
            f"sample_rate = {config.sample_rate}",
            f"channels = {config.channels}",
            f"max_record_seconds = {config.max_record_seconds}",
            f"hotkey = {_toml_string(config.hotkey)}",
            f"prompt = {_toml_string(config.prompt)}",
            "",
        ]
    )


def ensure_config_files() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        default = AppConfig(
            model=DEFAULT_MODEL,
            sample_rate=DEFAULT_SAMPLE_RATE,
            channels=DEFAULT_CHANNELS,
            max_record_seconds=DEFAULT_MAX_RECORD_SECONDS,
            hotkey=DEFAULT_HOTKEY,
            prompt=DEFAULT_PROMPT,
        )
        CONFIG_PATH.write_text(_format_config_toml(default), encoding="utf-8")

    if not CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.write_text(
            "\n".join(
                [
                    "# shruti credentials",
                    "# Keep this file private: chmod 600 ~/.config/shruti/credentials.toml",
                    '# api_key = "YOUR_GEMINI_API_KEY"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        os.chmod(CREDENTIALS_PATH, 0o600)


def load_config() -> AppConfig:
    ensure_config_files()
    raw = _parse_toml(CONFIG_PATH)
    hotkey = normalize_hotkey(str(raw.get("hotkey", DEFAULT_HOTKEY)))
    return AppConfig(
        model=str(raw.get("model", DEFAULT_MODEL)),
        sample_rate=int(raw.get("sample_rate", DEFAULT_SAMPLE_RATE)),
        channels=int(raw.get("channels", DEFAULT_CHANNELS)),
        max_record_seconds=int(raw.get("max_record_seconds", DEFAULT_MAX_RECORD_SECONDS)),
        hotkey=hotkey,
        prompt=str(raw.get("prompt", DEFAULT_PROMPT)),
    )


def save_config(config: AppConfig) -> None:
    ensure_config_files()
    normalized = AppConfig(
        model=config.model,
        sample_rate=config.sample_rate,
        channels=config.channels,
        max_record_seconds=config.max_record_seconds,
        hotkey=normalize_hotkey(config.hotkey),
        prompt=config.prompt,
    )
    CONFIG_PATH.write_text(_format_config_toml(normalized), encoding="utf-8")


def load_stored_api_key() -> str:
    ensure_config_files()
    _ensure_credentials_permissions()
    raw = _parse_toml(CREDENTIALS_PATH)
    return str(raw.get("api_key", "")).strip()


def save_api_key(api_key: str) -> None:
    ensure_config_files()
    cleaned = api_key.strip()
    CREDENTIALS_PATH.write_text(
        "\n".join(
            [
                "# shruti credentials",
                "# Keep this file private: chmod 600 ~/.config/shruti/credentials.toml",
                f"api_key = {_toml_string(cleaned)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(CREDENTIALS_PATH, 0o600)


def load_api_key() -> str:
    file_key = load_stored_api_key()
    if file_key:
        return file_key

    raise RuntimeError(f"Missing Gemini API key in {CREDENTIALS_PATH}.")
