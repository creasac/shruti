#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_SYSTEM_PACKAGES="${SKIP_SYSTEM_PACKAGES:-0}"
RUN_SETUP="${RUN_SETUP:-1}"

usage() {
  cat <<MSG
Usage: ./install.sh [options]

Options:
  --skip-system-packages   Skip apt/dnf/pacman dependency install
  --no-setup               Skip interactive 'shruti setup'
  --venv-dir PATH          Set virtualenv location (default: ./.venv)
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
      --venv-dir)
        VENV_DIR="$2"
        shift 2
        ;;
      --python)
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

  install_system_packages

  log "[shruti] Creating venv: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"

  log "[shruti] Installing package..."
  "$VENV_DIR/bin/pip" install --upgrade pip
  "$VENV_DIR/bin/pip" install -e "$ROOT_DIR"

  if [[ "$RUN_SETUP" == "1" ]]; then
    log "[shruti] Running interactive setup..."
    "$VENV_DIR/bin/shruti" setup
    echo "[shruti] Install complete."
  else
    echo "[shruti] Install complete. Run: $VENV_DIR/bin/shruti setup"
  fi
}

main "$@"
