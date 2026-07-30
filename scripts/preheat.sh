#!/usr/bin/env bash
# Starts the model servers and loads every model into memory, so the first
# dictation / practice / chat turn of a session is already warm.
#
# Only needed when RESTART_POLICY=no in .env (manual mode); with the default
# unless-stopped policy Docker does this at boot and the models stay resident.
# Pair with ./scripts/cooldown.sh to give the VRAM back.
#
# Usage: ./scripts/preheat.sh [--no-llm]
#   --no-llm   skip the ~11 GB qwen3 load (enough for `transcribe`/`speak`)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOAD_LLM=1
[ "${1:-}" = "--no-llm" ] && LOAD_LLM=0

# optional keys may be absent — grep failing must not kill the script
get() { { grep -E "^$1=" .env 2>/dev/null || true; } | head -1 | cut -d= -f2 | awk '{print $1}'; }
LLM_MODEL="$(get LLM_MODEL)"; LLM_MODEL="${LLM_MODEL:-qwen3:14b}"
ASR_PORT="$(get ASR_PORT)"; ASR_PORT="${ASR_PORT:-8001}"
TTS_PORT="$(get TTS_PORT)"; TTS_PORT="${TTS_PORT:-8002}"
LLM_PORT="$(get LLM_PORT)"; LLM_PORT="${LLM_PORT:-11434}"

FAIL=0
t0=$SECONDS

echo "==> starting containers"
docker compose up -d || exit 1

# ASR and TTS load their models in a background thread at startup and flip
# model_loaded once done; a first-ever start also downloads weights (~4 GB).
wait_loaded() {
    local name=$1 url=$2 deadline=$((SECONDS + 600))
    printf '  %-3s ' "$name"
    while [ "$SECONDS" -lt "$deadline" ]; do
        if curl -fsS "$url/health" 2>/dev/null | grep -q '"model_loaded": *true'; then
            echo " ready (${SECONDS}s)"
            return 0
        fi
        printf '.'
        sleep 2
    done
    echo " TIMEOUT — check: docker compose logs $name"
    FAIL=1
}

echo "==> waiting for models"
wait_loaded asr "http://127.0.0.1:$ASR_PORT"
wait_loaded tts "http://127.0.0.1:$TTS_PORT"

if [ "$LOAD_LLM" = 1 ]; then
    printf '  llm '
    deadline=$((SECONDS + 120))
    while [ "$SECONDS" -lt "$deadline" ]; do
        curl -fsS "http://127.0.0.1:$LLM_PORT/api/tags" >/dev/null 2>&1 && break
        printf '.'
        sleep 2
    done
    # empty prompt = load into VRAM and stop; keep_alive matches the app's own
    if curl -fsS "http://127.0.0.1:$LLM_PORT/api/generate" \
        -d "{\"model\":\"$LLM_MODEL\",\"prompt\":\"\",\"keep_alive\":\"30m\"}" >/dev/null 2>&1; then
        echo " $LLM_MODEL resident (${SECONDS}s)"
    else
        echo " FAILED to load $LLM_MODEL (pulled? ./scripts/pull_models.sh)"
        FAIL=1
    fi
else
    echo "  llm  skipped (--no-llm); it loads on first use, ~15 s"
fi

echo "==> warm in ${SECONDS}s"
command -v nvidia-smi >/dev/null && nvidia-smi \
    --query-gpu=memory.used,memory.total --format=csv,noheader | sed 's/^/  VRAM: /'
[ "$FAIL" = 0 ] || { echo "  (something did not come up — see above)"; exit 1; }
