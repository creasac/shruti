from __future__ import annotations

import argparse
import getpass
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from .config import (
    AppConfig,
    CREDENTIALS_PATH,
    CONFIG_PATH,
    ensure_config_files,
    load_api_key,
    load_config,
    load_stored_api_key,
    normalize_hotkey,
    save_api_key,
    save_config,
)

if TYPE_CHECKING:
    from .service import STTService


SERVICE_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_PATH = SERVICE_DIR / "shruti.service"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shruti", description="Minimal desktop speech-to-text utility.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create default config and credentials files.")
    sub.add_parser("setup", help="Interactive setup for API key, hotkey, and autostart.")

    doctor = sub.add_parser("doctor", help="Check local setup and dependencies.")
    doctor.add_argument("--verbose", action="store_true", help="Print extra diagnostics.")

    sub.add_parser(
        "transcribe",
        help="Record from microphone and print transcript.",
    )

    sub.add_parser("daemon", help="Run hotkey daemon for toggle recording and text insertion.")

    return parser


def cmd_init() -> int:
    ensure_config_files()
    print(f"Config created: {CONFIG_PATH}")
    print(f"Credentials template: {CREDENTIALS_PATH}")
    print("Run 'shruti setup' to configure API key, hotkey, and autostart.")
    return 0


def _record_interactive(service: STTService):
    service.recorder.start()
    print("Recording... press Enter to stop.")
    try:
        input()
    except KeyboardInterrupt:
        pass
    return service.recorder.stop()


def _prompt_yes_no(prompt: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{prompt} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.")


def _hotkey_is_valid(hotkey: str) -> bool:
    try:
        from pynput import keyboard

        keyboard.HotKey.parse(hotkey)
    except Exception:  # noqa: BLE001
        return False
    return True


def _hotkey_detectable(hotkey: str, timeout_seconds: float = 6.0) -> bool:
    from pynput import keyboard

    hit = threading.Event()
    hotkeys = keyboard.GlobalHotKeys({hotkey: lambda: hit.set()})
    hotkeys.start()
    try:
        print(f"Press {hotkey} now to verify it is not blocked by another shortcut.")
        return hit.wait(timeout_seconds)
    finally:
        hotkeys.stop()


def _prompt_hotkey(current_hotkey: str) -> str:
    print("Set the recording toggle hotkey.")
    print("Examples: <ctrl>+<space>, <ctrl>+<alt>+h")
    while True:
        raw = input(f"Hotkey [{current_hotkey}]: ").strip()
        chosen = normalize_hotkey(raw or current_hotkey)

        if not _hotkey_is_valid(chosen):
            print("Invalid hotkey format. Try again.")
            continue

        try:
            if _hotkey_detectable(chosen):
                return chosen
            print("That hotkey was not detected. It may conflict with a system/global shortcut.")
            if _prompt_yes_no("Use it anyway", default=False):
                return chosen
        except Exception as exc:  # noqa: BLE001
            print(f"Hotkey verification failed: {exc}")
            if _prompt_yes_no("Use this hotkey anyway", default=True):
                return chosen


def _prompt_api_key(existing_key: str) -> str:
    print("Enter your Gemini API key (input hidden).")
    if existing_key:
        print("Press Enter to keep your existing saved key.")

    while True:
        value = getpass.getpass("Gemini API key: ").strip()
        if value:
            return value
        if existing_key:
            return existing_key
        print("API key is required.")


def _write_service_file(shruti_exe: Path) -> Path:
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)
    service_body = "\n".join(
        [
            "[Unit]",
            "Description=Shruti speech-to-text daemon",
            "After=graphical-session.target",
            "",
            "[Service]",
            "Type=simple",
            f"ExecStart={shruti_exe} daemon",
            "Restart=on-failure",
            "RestartSec=2",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )
    SERVICE_PATH.write_text(service_body, encoding="utf-8")
    return SERVICE_PATH


def _enable_autostart(shruti_exe: Path) -> tuple[bool, str]:
    service_file = _write_service_file(shruti_exe)
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "shruti.service"], check=True)
        return True, f"Autostart enabled via {service_file}"
    except FileNotFoundError:
        return False, f"systemctl not found; service file written to {service_file}"
    except subprocess.CalledProcessError as exc:
        return False, f"Could not enable autostart automatically ({exc}); service file written to {service_file}"


def cmd_setup(_args: argparse.Namespace) -> int:
    ensure_config_files()
    current = load_config()
    existing_key = load_stored_api_key()

    print("shruti setup")
    print("- Esc always cancels recording")
    print(f"- Max recording length is {current.max_record_seconds} seconds")

    api_key = _prompt_api_key(existing_key)
    hotkey = _prompt_hotkey(current.hotkey)

    updated = AppConfig(
        model=current.model,
        sample_rate=current.sample_rate,
        channels=current.channels,
        max_record_seconds=current.max_record_seconds,
        hotkey=hotkey,
        prompt=current.prompt,
    )
    save_config(updated)
    save_api_key(api_key)

    autostart_enabled = False
    autostart_msg = "Autostart not configured"
    if _prompt_yes_no("Enable daemon autostart at login", default=True):
        autostart_enabled, autostart_msg = _enable_autostart(Path(sys.argv[0]).resolve())

    print("\nSetup complete.")
    print(f"Hotkey: {updated.hotkey} (start/stop recording)")
    print("Esc: cancel current recording")
    print(f"Max recording: {updated.max_record_seconds} seconds")
    print(autostart_msg)

    if autostart_enabled:
        print("Daemon is running now and will start on login.")
    else:
        print("Start manually with: shruti daemon")

    return 0


def cmd_transcribe(_args: argparse.Namespace) -> int:
    from .service import STTService

    config = load_config()
    api_key = load_api_key()
    service = STTService(config=config, api_key=api_key)

    recording = _record_interactive(service)
    result = service.transcribe_bytes(recording.data, duration_seconds=recording.duration_seconds)

    print(result.text)
    return 0


def cmd_daemon(_args: argparse.Namespace) -> int:
    try:
        from .daemon import DaemonOptions, STTDaemon
        from .service import STTService

        config = load_config()
        api_key = load_api_key()
        service = STTService(config=config, api_key=api_key)
        daemon = STTDaemon(service=service, options=DaemonOptions(insert_text=True))
        print(f"shruti daemon running. Hotkey: {config.hotkey}. Ctrl+C to quit.")
        daemon.start()
    except KeyboardInterrupt:
        print("\nshruti daemon stopped.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to start daemon: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ensure_config_files()
    print(f"Config path: {CONFIG_PATH}")
    print(f"Credentials path: {CREDENTIALS_PATH}")
    print(f"DISPLAY={_safe_env('DISPLAY')}")
    print(f"XDG_SESSION_TYPE={_safe_env('XDG_SESSION_TYPE')}")

    missing: list[str] = []
    try:
        config = load_config()
        print(f"Hotkey: {config.hotkey}")
        print(f"Max recording: {config.max_record_seconds} seconds")
    except Exception as exc:  # noqa: BLE001
        missing.append(f"config: {exc}")

    try:
        load_api_key()
        print("API key: found")
    except Exception as exc:  # noqa: BLE001
        missing.append(f"api-key: {exc}")

    try:
        from .x11_insert import ensure_xdotool

        ensure_xdotool()
        print("xdotool: found")
    except Exception as exc:  # noqa: BLE001
        missing.append(f"xdotool: {exc}")

    if args.verbose:
        print(f"Python: {sys.version.split()[0]}")

    if missing:
        print("Issues:")
        for item in missing:
            print(f"- {item}")
        return 1

    print("Doctor check passed.")
    return 0


def _safe_env(name: str) -> str:
    import os

    return os.getenv(name, "")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, signal.default_int_handler)

    if args.command == "init":
        return cmd_init()
    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "transcribe":
        return cmd_transcribe(args)
    if args.command == "daemon":
        return cmd_daemon(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
