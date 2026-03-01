from __future__ import annotations

import argparse
import fcntl
import getpass
import os
import re
import signal
import subprocess
import sys
import threading
import time
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
    from .audio import RecordingResult
    from .overlay import Overlay
    from .service import STTService


ONESHOT_LOCK_PATH = Path("/tmp/shruti-oneshot.lock")
ONESHOT_PID_PATH = Path("/tmp/shruti-oneshot.pid")

GNOME_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_BINDING_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
GNOME_BINDING_PATH = f"{GNOME_BINDING_BASE}shruti/"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shruti", description="Minimal desktop speech-to-text utility.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Interactive setup for API key and global shortcut trigger.")

    doctor = sub.add_parser("doctor", help="Check local setup and dependencies.")
    doctor.add_argument("--verbose", action="store_true", help="Print extra diagnostics.")

    sub.add_parser("transcribe", help="Record from microphone and print transcript.")
    sub.add_parser("oneshot", help="One-shot run triggered by global shortcut.")

    return parser


def _record_interactive(service: STTService) -> RecordingResult:
    service.recorder.start()
    print("Recording... press Enter to stop.")
    try:
        input()
    except KeyboardInterrupt:
        pass
    return service.recorder.stop()


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
    print("Set the recording trigger hotkey.")
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
            print("That hotkey was not detected. It may conflict with another global shortcut.")
            print("Choose a different hotkey.")
        except Exception as exc:  # noqa: BLE001
            print(f"Hotkey verification failed ({exc}). Keeping selected hotkey.")
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


def _hotkey_to_gnome_accelerator(hotkey: str) -> str:
    tokens = [token.strip() for token in hotkey.split("+") if token.strip()]
    modifiers: list[str] = []
    key = ""

    for token in tokens:
        lower = token.strip("<>").lower()
        if lower in {"ctrl", "control"}:
            modifiers.append("<Control>")
        elif lower == "shift":
            modifiers.append("<Shift>")
        elif lower == "alt":
            modifiers.append("<Alt>")
        elif lower in {"super", "windows", "cmd"}:
            modifiers.append("<Super>")
        else:
            key = "space" if lower == "space" else lower

    if not key:
        raise RuntimeError(f"Hotkey '{hotkey}' does not include a final key.")
    return "".join(modifiers) + key


def _gsettings_get_custom_bindings() -> list[str]:
    proc = subprocess.run(
        ["gsettings", "get", GNOME_SCHEMA, "custom-keybindings"],
        check=True,
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    return re.findall(r"'([^']+)'", out)


def _gsettings_set_string(schema: str, key: str, value: str) -> None:
    subprocess.run(["gsettings", "set", schema, key, repr(value)], check=True)


def _configure_gnome_hotkey(shruti_exe: Path, hotkey: str) -> tuple[bool, str]:
    accel = _hotkey_to_gnome_accelerator(hotkey)
    cmd = f"{shruti_exe} oneshot"

    bindings = _gsettings_get_custom_bindings()
    if GNOME_BINDING_PATH not in bindings:
        bindings.append(GNOME_BINDING_PATH)
        list_value = "[" + ", ".join(repr(b) for b in bindings) + "]"
        subprocess.run(["gsettings", "set", GNOME_SCHEMA, "custom-keybindings", list_value], check=True)

    schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{GNOME_BINDING_PATH}"
    _gsettings_set_string(schema, "name", "shruti")
    _gsettings_set_string(schema, "command", cmd)
    _gsettings_set_string(schema, "binding", accel)

    return True, f"Configured GNOME shortcut {accel} -> {cmd}"


def _configure_hotkey_trigger(shruti_exe: Path, hotkey: str) -> tuple[bool, str]:
    try:
        return _configure_gnome_hotkey(shruti_exe, hotkey)
    except FileNotFoundError:
        return False, f"gsettings not found. Configure a system shortcut manually to run: {shruti_exe} oneshot"
    except subprocess.CalledProcessError as exc:
        return False, (
            "Could not configure GNOME shortcut automatically. "
            f"Configure a system shortcut manually to run: {shruti_exe} oneshot (error: {exc})"
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not configure system shortcut automatically: {exc}"


def cmd_setup(_args: argparse.Namespace) -> int:
    ensure_config_files()
    current = load_config()
    existing_key = load_stored_api_key()

    print("shruti setup")
    print("- Esc always cancels recording")
    print(f"- Max recording length is {current.max_record_seconds} seconds")
    print("- Nothing runs in background while idle")

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

    ok, msg = _configure_hotkey_trigger(Path(sys.argv[0]).resolve(), updated.hotkey)

    print("\nSetup complete.")
    print(f"Hotkey: {updated.hotkey} (press once to start, again to stop)")
    print("Esc: cancel current recording")
    print(f"Max recording: {updated.max_record_seconds} seconds")
    print(msg)

    return 0 if ok else 1


def _acquire_oneshot_lock() -> int | None:
    fd = os.open(ONESHOT_LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def _release_oneshot_lock(fd: int | None) -> None:
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    os.close(fd)


def _signal_active_oneshot() -> bool:
    try:
        pid = int(ONESHOT_PID_PATH.read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001
        return False

    try:
        os.kill(pid, signal.SIGUSR1)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _record_oneshot(service: STTService, overlay: Overlay, stop_event: threading.Event) -> tuple[RecordingResult | None, bool]:
    from pynput import keyboard

    cancel = threading.Event()

    def on_press(key: keyboard.KeyCode | keyboard.Key | None) -> None:
        if key == keyboard.Key.esc:
            cancel.set()

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    service.recorder.start()
    start = time.time()

    try:
        while True:
            if cancel.is_set():
                try:
                    service.recorder.stop()
                except Exception:  # noqa: BLE001
                    pass
                overlay.show(kind="cancelled", sticky=False)
                return None, True

            elapsed = time.time() - start
            bars = service.recorder.waveform_bars(bars=56)
            overlay.show(kind="recording", sticky=True, bars=bars)

            if stop_event.is_set() or elapsed >= service.config.max_record_seconds:
                break

            time.sleep(0.05)

        recording = service.recorder.stop()
        return recording, False
    finally:
        listener.stop()


def cmd_oneshot(_args: argparse.Namespace) -> int:
    from .overlay import Overlay
    from .service import STTService

    lock_fd = _acquire_oneshot_lock()
    if lock_fd is None:
        _signal_active_oneshot()
        return 0

    stop_event = threading.Event()

    def on_stop_signal(_signum: int, _frame: object) -> None:
        stop_event.set()

    old_handler = signal.signal(signal.SIGUSR1, on_stop_signal)

    overlay: Overlay | None = None

    try:
        ONESHOT_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
        config = load_config()
        api_key = load_api_key()
        service = STTService(config=config, api_key=api_key)
        overlay = Overlay()
        overlay.start()

        recording, cancelled = _record_oneshot(service, overlay, stop_event)
        if cancelled or recording is None:
            return 0

        overlay.show(kind="transcribing", sticky=True)
        result = service.transcribe_bytes(recording.data, duration_seconds=recording.duration_seconds)
        service.insert_text(result.text)
        overlay.show(kind="done", sticky=False)
        return 0
    except Exception as exc:  # noqa: BLE001
        if overlay is not None:
            try:
                overlay.show(kind="error", sticky=False)
            except Exception:  # noqa: BLE001
                pass
        print(f"oneshot failed: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGUSR1, old_handler)
        try:
            if ONESHOT_PID_PATH.exists():
                ONESHOT_PID_PATH.unlink()
        except OSError:
            pass
        _release_oneshot_lock(lock_fd)


def cmd_transcribe(_args: argparse.Namespace) -> int:
    from .service import STTService

    config = load_config()
    api_key = load_api_key()
    service = STTService(config=config, api_key=api_key)

    recording = _record_interactive(service)
    result = service.transcribe_bytes(recording.data, duration_seconds=recording.duration_seconds)

    print(result.text)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ensure_config_files()
    print(f"Config path: {CONFIG_PATH}")
    print(f"Credentials path: {CREDENTIALS_PATH}")
    print(f"DISPLAY={os.getenv('DISPLAY', '')}")
    print(f"XDG_SESSION_TYPE={os.getenv('XDG_SESSION_TYPE', '')}")

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

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, signal.default_int_handler)

    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "transcribe":
        return cmd_transcribe(args)
    if args.command == "oneshot":
        return cmd_oneshot(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
