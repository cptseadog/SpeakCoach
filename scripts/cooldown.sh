#!/usr/bin/env bash
# Stops the model servers and gives the VRAM back. Containers are stopped, not
# removed, so ./scripts/preheat.sh restarts them without re-downloading weights.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

get() { { grep -E "^$1=" .env 2>/dev/null || true; } | head -1 | cut -d= -f2 | awk '{print $1}'; }
LLM_PORT="$(get LLM_PORT)"; LLM_PORT="${LLM_PORT:-11434}"
LLM_MODEL="$(get LLM_MODEL)"; LLM_MODEL="${LLM_MODEL:-qwen3:14b}"

# ask Ollama to unload first so it flushes VRAM cleanly rather than being killed
curl -fsS "http://127.0.0.1:$LLM_PORT/api/generate" \
    -d "{\"model\":\"$LLM_MODEL\",\"prompt\":\"\",\"keep_alive\":0}" >/dev/null 2>&1 || true

docker compose stop
command -v nvidia-smi >/dev/null && nvidia-smi \
    --query-gpu=memory.used,memory.total --format=csv,noheader | sed 's/^/VRAM now: /'
