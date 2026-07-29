#!/usr/bin/env bash
# Pulls the Ollama model(s) named in .env into the llm container's volume.
# (ASR/TTS weights download themselves on first container start; only Ollama
# models need an explicit pull.) Run after: docker compose up -d
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# optional keys may be absent — grep failing must not kill the script (set -e)
get() { { grep -E "^$1=" .env 2>/dev/null || true; } | head -1 | cut -d= -f2 | awk '{print $1}'; }

LLM_MODEL="$(get LLM_MODEL)"; LLM_MODEL="${LLM_MODEL:-qwen3:14b}"
DICTATION_MODEL="$(get DICTATION_MODEL)"

docker compose exec -T llm ollama pull "$LLM_MODEL"
if [ -n "$DICTATION_MODEL" ] && [ "$DICTATION_MODEL" != "$LLM_MODEL" ]; then
    docker compose exec -T llm ollama pull "$DICTATION_MODEL"
fi
docker compose exec -T llm ollama list
