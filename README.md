# SpeakCoach

A local, always-available English speaking assistant with two deliberately separated jobs:

- **Job A — Dictation (hot path):** push-to-talk → ASR → light cleanup → text lands on the clipboard, ready to paste into any focused text box. No spoken feedback, nothing heavy in the loop.
- **Job B — Coaching (cold path):** every utterance is logged; practice sessions and a daily mini-lesson analyze recurring mistakes, explain them, and read corrections back via TTS.

## Architecture

**Containers do model math; the host talks to the OS.**

| Component | Where | What |
|---|---|---|
| ASR | Docker, `:8001` | faster-whisper (`large-v3` on GPU / `distil-large-v3` on CPU), `/v1/audio/transcriptions` |
| LLM | Docker, `:11434` | Ollama (`qwen3:14b`), native `/api/chat` with `think=false` on the hot path |
| TTS | Docker, `:8002` | Kokoro-82M (US voice `af_heart`), `/v1/audio/speech`; stays on CPU by design¹ |
| Host client | native (uv venv) | mic, push-to-talk trigger, Wayland text injection, SQLite |

¹ Kokoro is faster than realtime on CPU and the 16 GB of VRAM is fully budgeted for the LLM (~11 GB) + whisper large-v3 (~3 GB).

The host client is **not** dockerized — it owns the microphone, speakers, trigger, and clipboard. Services bind to `127.0.0.1` only.

## Setting up on a fresh machine

What git does *not* carry, and where it comes from:

| Not in git | How it appears |
|---|---|
| `.env` | `scripts/install_host.sh` copies it from `.env.example`; edit to taste |
| Docker volumes (`asr-models`, `tts-models`, `ollama-models`) | created automatically by `docker compose up`; **never create them manually** |
| ASR + TTS weights (~4 GB) | each container downloads into its volume on first start |
| Ollama models (~9 GB for qwen3:14b) | one explicit step: `./scripts/pull_models.sh` |
| SQLite DB / retained audio | created on first use at `DB_PATH` (default `~/.local/share/speakcoach/`) |

Nothing in this project installs a system-level autostart. The only thing that
brings the services up at boot is Docker's own `restart` policy — see
[Starting and stopping the stack](#starting-and-stopping-the-stack).

Steps:

```bash
git clone <repo> && cd spoken-english-tutor
./scripts/install_host.sh        # checks prereqs, creates .env — review it
docker compose up -d --build     # first start downloads ASR/TTS weights (watch /health)
./scripts/pull_models.sh         # pulls the Ollama model(s) from .env
(cd host_client && uv sync)
python3 scripts/healthcheck.py   # everything must be green
```

Host prerequisites (the install script checks these): Docker + compose plugin, [uv](https://docs.astral.sh/uv/), `wl-clipboard`, `libportaudio2`. The stack must run CPU-only first (`DEVICE=cpu`, the default) on any machine; GPU is opt-in config:

### GPU (NVIDIA, tested on RTX 5070 Ti / sm_120)

1. Install the NVIDIA driver and [container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
2. In `.env`: `DEVICE=cuda`, `ASR_MODEL=large-v3`, and uncomment
   `COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml`.
3. `docker compose up -d --build`, then `python3 scripts/healthcheck.py` — it must print the GPU and its compute capability (12.0 here), and the asr health must say `"device": "cuda"`.

⚠️ Blackwell/sm_120 note: anything using PyTorch needs CUDA 12.8+ / cu128 wheels / torch ≥ 2.7. The current images sidestep this (ASR uses CTranslate2 + pip-provided cuBLAS/cuDNN; TTS stays on CPU) — it only bites if you move Kokoro to the GPU.

Measured hot-path latency (RTX 5070 Ti, warm): ASR 0.26 s for 6 s of speech + cleanup 0.4 s ≈ **under 1 s** from stop-speaking to clipboard. CPU-only for reference: ~10 s.

## Starting and stopping the stack

`RESTART_POLICY` in `.env` decides who starts the model servers:

| `RESTART_POLICY` | Behaviour | Idle cost |
|---|---|---|
| `unless-stopped` (default) | Docker starts all three at boot; models stay resident | ~4 GB VRAM (ASR); LLM unloads after its 30 min `keep_alive` |
| `no` | nothing starts by itself — you drive it | 0 |

Manual mode:

```bash
./scripts/preheat.sh            # start + load every model (~23 s cold, 0 s if already warm)
./scripts/preheat.sh --no-llm   # skip the ~11 GB qwen3 load (enough for transcribe/speak)
./scripts/cooldown.sh           # unload the LLM, stop the containers, free the VRAM
```

Both scripts are idempotent and safe to alias. Containers are stopped, not
removed, so nothing re-downloads. Changing `RESTART_POLICY` takes effect on the
next `docker compose up -d` (it recreates the containers). Warm from cold:
ASR 4 s, TTS 9 s, qwen3:14b 23 s → 13.5/16 GB VRAM.

## Daily use

### Dictation

```bash
cd host_client && uv run speakcoach dictate     # or install the systemd unit below
```

Toggle recording with **Enter** in that terminal, from anywhere via a GNOME custom
shortcut (Settings → Keyboard → Custom Shortcuts) bound to
`sh -c 'kill -USR1 $(cat /run/user/1000/speakcoach-dictate.pid)'`, or with
`speakcoach toggle`. Speak, toggle again, **Ctrl+V**. Desktop notifications confirm
each step; silent recordings are gated out (Whisper hallucinates on silence).

Every utterance (raw + cleaned) is logged to SQLite at `DB_PATH`; `speakcoach log`
shows recent entries; `AUDIO_KEEP=true` retains WAVs for a future pronunciation v2.

Always-on: `cp systemd/speakcoach.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now speakcoach`

### Practice & lessons

- `uv run speakcoach practice` — speak; get corrections with explanations, a native-idiomatic alternative, spoken read-back; mistakes land in SQLite.
- `uv run speakcoach lesson` — one mini-lesson from your most frequent recent mistake categories (needs ≥3 logged mistakes; idempotent per day). Automate at 08:00: `cp systemd/speakcoach-lesson.{service,timer} ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now speakcoach-lesson.timer`

### Chat (free conversation practice)

```bash
uv run speakcoach chat                # voice: Enter to record, Enter to stop, Ctrl+C to end
uv run speakcoach chat --text         # typed REPL instead
uv run speakcoach chat --correct      # partner gently recasts your errors while chatting
uv run speakcoach chat --api          # use the OpenAI-compatible API from .env
```

A natural conversation partner (local qwen3:14b by default) that knows your goal and
a profile built from your logged mistakes. Replies are printed and read aloud.
Ending the session (Ctrl+C) runs the local coach over your turns — mistakes land in
the same DB that feeds daily lessons — and the chat model writes a short session note.
For the API backend set `CHAT_API_BASE_URL`, `CHAT_API_KEY`, and `CHAT_API_MODEL`
in `.env` (works with any OpenAI-compatible provider); `--model` overrides per session.

### ydotool auto-type (optional — you probably don't want this)

`INJECTION_BACKEND=clipboard` (wl-clipboard, the default) copies the transcript and
you press **Ctrl+V**. It needs no daemon, no elevated device access, and no
package beyond `wl-clipboard`. **Nothing in SpeakCoach requires ydotool** — it is
purely a convenience for having text typed straight into the focused field.

⚠️ **Read this before installing it.** On Ubuntu, `apt install ydotool` registers
its user service *globally* (`/etc/systemd/user/default.target.wants/ydotool.service`),
so `ydotoold` tries to start for every user at every login. It then fails with
`status=2/INVALIDARGUMENT` because `/dev/uinput` is `root:input` `0660` and your
account is not in the `input` group — giving you a permanently failing unit and a
noisy boot for a feature you may not even use. The package's own udev rule
(`/usr/lib/udev/rules.d/80-uinput.rules`) sets the group but cannot add you to it.

If you install it, the group membership is the step that matters:

```bash
sudo apt install ydotool
sudo usermod -aG input $USER     # without this, ydotoold exits 2 at every login
# log out and back in (group changes need a fresh session), then:
systemctl --user enable --now ydotool.service
```

and set `INJECTION_BACKEND=ydotool` in `.env`. Verify with
`systemctl --user status ydotool.service` — it must be `active (running)`.

To remove it again:

```bash
systemctl --user disable --now ydotool.service   # or: --user mask, if enabled globally
sudo apt purge --autoremove ydotool
systemctl --user unmask ydotool.service          # only if you masked it
```

Either way dictation keeps working: selecting `ydotool` when the binary is absent
logs a warning and uses the clipboard, and if `ydotoold` dies mid-session the
transcript is copied to the clipboard rather than lost.

## Status of the Project

All nine milestones from the project brief (`claude_code_prompt.md`) are complete:
skeleton/healthcheck, Kokoro TTS, faster-whisper ASR + mic capture, dictation hot
path, SQLite logging, coaching path, daily lessons, GPU flip (verified sm_120),
ydotool backend + systemd units. No pronunciation scoring in v1 by design (ASR text
masks mispronunciation); `pronunciation.py` holds the v2 extension point.

Planned next: split deployment — this machine as headless model server, the host
client on a laptop over Tailscale/SSH (only the three service URLs in `.env` change).
