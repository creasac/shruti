#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/creasac/shruti.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/share/shruti}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

if ! need_cmd git; then
  echo "[shruti] git is required for bootstrap install." >&2
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_DIR")"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "[shruti] Updating existing checkout at $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "[shruti] Cloning to $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
./install.sh
