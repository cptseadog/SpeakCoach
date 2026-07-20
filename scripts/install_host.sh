#!/usr/bin/env bash
# Host prerequisites check for the native client. Never runs sudo itself —
# it prints the commands for you to review and run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== SpeakCoach host setup =="

if [ ! -f "$REPO_ROOT/.env" ]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "Created .env from .env.example — review it."
else
    echo ".env already exists — leaving it alone."
fi

missing_apt=()
command -v wl-copy >/dev/null || missing_apt+=(wl-clipboard)
dpkg -s libportaudio2 >/dev/null 2>&1 || missing_apt+=(libportaudio2)

echo
command -v uv >/dev/null \
    && echo "[ok] uv" \
    || echo "[missing] uv — install: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v docker >/dev/null \
    && echo "[ok] docker" \
    || echo "[missing] docker — see https://docs.docker.com/engine/install/ubuntu/"
docker compose version >/dev/null 2>&1 \
    && echo "[ok] docker compose" \
    || echo "[missing] docker compose plugin"

if [ ${#missing_apt[@]} -gt 0 ]; then
    echo "[missing] apt packages — run: sudo apt install ${missing_apt[*]}"
else
    echo "[ok] wl-clipboard, libportaudio2"
fi

echo
echo "Then: (cd host_client && uv sync) and docker compose up -d"
