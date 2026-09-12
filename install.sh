#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/shruti"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_SYSTEM_PACKAGES="${SKIP_SYSTEM_PACKAGES:-0}"
RUN_SETUP="${RUN_SETUP:-1}"

usage() {
  cat <<MSG
Usage: ./install.sh [options]

Options:
  --skip-system-packages   Skip apt/dnf/pacman dependency install
  --no-setup               Skip interactive 'shruti setup'
  --python PATH            Python binary to use (default: python3)
  -h, --help               Show this help
MSG
}

log() {
  printf '%s\n' "$*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-system-packages)
        SKIP_SYSTEM_PACKAGES="1"
        shift
        ;;
      --no-setup)
        RUN_SETUP="0"
        shift
        ;;
      --python)
        [[ $# -ge 2 && -n "$2" ]] || { log "[shruti] --python requires a path"; exit 1; }
        PYTHON_BIN="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        log "[shruti] Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done
}

install_system_packages() {
  if [[ "$SKIP_SYSTEM_PACKAGES" == "1" ]]; then
    log "[shruti] Skipping system package install."
    return 0
  fi

  if need_cmd apt-get; then
    log "[shruti] Installing system packages with apt-get..."
    sudo apt-get update
    sudo apt-get install -y xdotool portaudio19-dev python3-tk python3-venv
    return 0
  fi

  if need_cmd dnf; then
    log "[shruti] Installing system packages with dnf..."
    sudo dnf install -y xdotool portaudio-devel python3-tkinter
    return 0
  fi

  if need_cmd pacman; then
    log "[shruti] Installing system packages with pacman..."
    sudo pacman -S --needed xdotool portaudio tk
    return 0
  fi

  log "[shruti] Could not detect apt-get, dnf, or pacman."
  log "[shruti] Install these manually: xdotool, PortAudio dev package, and Tk for Python."
}

main() {
  parse_args "$@"

  if [[ ! -f "$ROOT_DIR/pyproject.toml" ]]; then
    log "[shruti] pyproject.toml not found in $ROOT_DIR"
    log "[shruti] Run this installer from the shruti repository root."
    exit 1
  fi

  log "[shruti] Root: $ROOT_DIR"
  if ! need_cmd "$PYTHON_BIN"; then
    log "[shruti] Missing Python binary: $PYTHON_BIN"
    exit 1
  fi

  "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Shruti requires Python 3.11 or newer.")'

  if [[ -e "$INSTALL_DIR/.git" || -L "$INSTALL_DIR" ]]; then
    log "[shruti] $INSTALL_DIR contains a legacy checkout or is a symlink."
    log "[shruti] Move it aside before installing; your configuration is in ~/.config/shruti."
    exit 1
  fi
  for name in shruti shruti-uninstall; do
    target="$VENV_DIR/bin/shruti"
    [[ "$name" != shruti-uninstall ]] || target="$INSTALL_DIR/uninstall.py"
    if [[ -e "$BIN_DIR/$name" || -L "$BIN_DIR/$name" ]]; then
      if [[ ! -L "$BIN_DIR/$name" || "$(readlink "$BIN_DIR/$name")" != "$target" ]]; then
        log "[shruti] Refusing to replace an unrelated command: $BIN_DIR/$name"
        exit 1
      fi
    fi
  done

  install_system_packages

  log "[shruti] Creating venv: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"

  log "[shruti] Installing package..."
  "$VENV_DIR/bin/python" -m pip install --no-cache-dir "$ROOT_DIR"

  mkdir -p "$BIN_DIR"
  install -m 755 "$ROOT_DIR/uninstall.py" "$INSTALL_DIR/uninstall.py"
  ln -sfn "$VENV_DIR/bin/shruti" "$BIN_DIR/shruti"
  ln -sfn "$INSTALL_DIR/uninstall.py" "$BIN_DIR/shruti-uninstall"

  log "[shruti] Installed: $BIN_DIR/shruti"
  log "[shruti] Uninstall: $BIN_DIR/shruti-uninstall [--purge]"
  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) log '[shruti] Add ~/.local/bin to your shell PATH: export PATH="$HOME/.local/bin:$PATH"' ;;
  esac

  if [[ "$RUN_SETUP" == "1" ]] && ( : </dev/tty ) 2>/dev/null; then
    log "[shruti] Running interactive setup..."
    # stdin may contain this installer when invoked through curl | bash.
    "$BIN_DIR/shruti" setup </dev/tty
  else
    log "[shruti] Run setup from a desktop terminal: $BIN_DIR/shruti setup"
  fi
}

main "$@"
