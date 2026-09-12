#!/usr/bin/env python3
"""Remove the per-user install without importing (or recreating) user config."""
from __future__ import annotations

import argparse
import ast
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys

GNOME_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_BINDING_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/shruti/"
LOCK_PATH = Path("/tmp/shruti-oneshot.lock")
PID_PATH = Path("/tmp/shruti-oneshot.pid")


def gsettings(*args: str) -> str:
    return subprocess.run(
        ["gsettings", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def get_bindings() -> list[str]:
    value = gsettings("get", GNOME_SCHEMA, "custom-keybindings")
    if value.startswith("@as "):
        value = value[4:]
    bindings = ast.literal_eval(value)
    if not isinstance(bindings, list) or not all(isinstance(b, str) for b in bindings):
        raise RuntimeError("Unexpected GNOME shortcut settings; leaving them unchanged.")
    return bindings


def remove_gnome_shortcut() -> None:
    if shutil.which("gsettings") is None:
        print("GNOME settings are unavailable. Remove any manually configured shortcut yourself.")
        return
    if GNOME_SCHEMA not in gsettings("list-schemas").splitlines():
        return
    bindings = get_bindings()
    if GNOME_BINDING_PATH in bindings:
        remaining = [b for b in bindings if b != GNOME_BINDING_PATH]
        gsettings("set", GNOME_SCHEMA, "custom-keybindings", repr(remaining))
        if get_bindings() != remaining:
            raise RuntimeError("GNOME did not save the shortcut removal. Run from your desktop session.")
    schema = f"{GNOME_SCHEMA}.custom-keybinding:{GNOME_BINDING_PATH}"
    gsettings("reset-recursively", schema)
    print("Removed Shruti's GNOME shortcut; other shortcuts were preserved.")


def remove_link(path: Path, target: Path) -> None:
    if path.is_symlink() and path.readlink() == target:
        path.unlink()
    elif path.exists() or path.is_symlink():
        print(f"Kept unrelated command: {path}")


def remove_tree(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def lock_runtime() -> int | None:
    """Refuse to uninstall during a recording; never signal a stale PID."""
    try:
        fd = os.open(LOCK_PATH, os.O_RDWR | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    if os.fstat(fd).st_uid != os.getuid():
        os.close(fd)
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError("Shruti is recording. Stop or cancel it, then run uninstall again.") from None
    return fd


def remove_runtime() -> None:
    for path in (PID_PATH, LOCK_PATH):
        try:
            if path.lstat().st_uid == os.getuid():
                path.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Uninstall Shruti for the current user.")
    parser.add_argument("--purge", action="store_true", help="Also delete configuration and the saved Gemini API key.")
    args = parser.parse_args(argv)
    app_dir = Path.home() / ".local" / "share" / "shruti"
    bin_dir = Path.home() / ".local" / "bin"
    config_dir = Path.home() / ".config" / "shruti"
    fd = None
    try:
        if (app_dir / ".git").exists() or app_dir.is_symlink():
            raise RuntimeError(f"{app_dir} is a legacy checkout or symlink. Move it aside before uninstalling.")
        fd = lock_runtime()
        # Do desktop cleanup first so a failure leaves the app and uninstaller usable.
        remove_gnome_shortcut()
        remove_link(bin_dir / "shruti", app_dir / "venv" / "bin" / "shruti")
        remove_link(bin_dir / "shruti-uninstall", app_dir / "uninstall.py")
        remove_runtime()
        remove_tree(app_dir)
        if args.purge:
            remove_tree(config_dir)
            print("Removed Shruti, configuration, and the locally saved Gemini API key.")
        else:
            print(f"Removed Shruti. Configuration and any saved Gemini API key were preserved in {config_dir}.")
            print("To purge them after uninstall, run:")
            print("  curl -fsSL https://raw.githubusercontent.com/creasac/shruti/master/uninstall.py | python3 - --purge")
        print("System packages were left installed.")
        return 0
    except (OSError, ValueError, SyntaxError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Uninstall failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if fd is not None:
            os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
