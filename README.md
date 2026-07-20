# SpeakCoach

A local, always-available English speaking assistant with two deliberately separated jobs:

- **Job A — Dictation (hot path):** push-to-talk → ASR → light cleanup → text lands on the clipboard, ready to paste into any focused text box. No spoken feedback, nothing heavy in the loop.
- **Job B — Coaching (cold path):** every utterance is logged; practice sessions and a daily mini-lesson analyze recurring mistakes, explain them, and read corrections back via TTS.

## Architecture

**Containers do model math; the host talks to the OS.**

| Component | Where | What |
|---|---|---|
| ASR | Docker, `:8001` | faster-whisper (`distil-large-v3`), OpenAI-compatible `/v1/audio/transcriptions` |
| LLM | Docker, `:11434` | Ollama (`qwen3:14b`), OpenAI-compatible `/v1` |
| TTS | Docker, `:8002` | Kokoro-82M (US voice `af_heart`), `/v1/audio/speech`; Piper fallback |
| Host client | native (uv venv) | mic, VAD, push-to-talk hotkey, Wayland text injection, SQLite |

The host client is **not** dockerized — it owns the microphone, speakers, global hotkey, and clipboard. The session is Wayland, so injection uses `wl-clipboard` (copy → you press Ctrl+V) by default, with an opt-in `ydotool` auto-type backend later.

## Quickstart (CPU-only works today)

```bash
./scripts/install_host.sh          # checks prereqs, creates .env
docker compose build && docker compose up -d
cd host_client && uv sync
uv run python ../scripts/healthcheck.py
```

Healthcheck green = every service reachable. Model endpoints return 503 until their milestone lands.

## GPU flip (when the RTX 5060 Ti arrives — Milestone 8)

1. Install the NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
2. Set `DEVICE=cuda` in `.env`.
3. `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`
4. `python3 scripts/healthcheck.py` — must report compute capability **12.0** (sm_120).

⚠️ Blackwell/sm_120: any image using PyTorch must be CUDA 12.8+ with cu128 wheels and torch ≥ 2.7. Older wheels fail with "no kernel image is available".

## Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Skeleton + healthcheck | ✅ |
| 2 | TTS service (Kokoro) + speak-a-sentence CLI | ✅ |
| 3 | ASR service + mic capture (hotkey → transcript in terminal) | — |
| 4 | **Dictation hot path** (first daily-usable build) | — |
| 5 | Utterance logging | — |
| 6 | Coaching path (structured mistakes → SQLite, TTS read-back) | — |
| 7 | Daily lesson + systemd timer | — |
| 8 | GPU flip + latency tuning | — |
| 9 | ydotool backend + always-on systemd service | — |

Design decisions, data model, and constraints live in `claude_code_prompt.md`. No pronunciation scoring in v1 (ASR text masks mispronunciation); `pronunciation.py` holds the v2 extension point.
