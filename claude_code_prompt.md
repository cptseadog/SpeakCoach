# Project Brief for Claude Code — "SpeakCoach": a local speech-to-corrected-text English coach

You are building a local, always-available English speaking assistant on my machine. Read this whole brief, then propose a plan and a repo skeleton **before** writing code. Ask me the open questions listed at the bottom; do not guess on those.

---

## 1. Goal (two jobs, deliberately separated)

**Job A — Dictation (hot path, ships first):** I speak; you transcribe; you do *light* cleanup (fix clear errors, add punctuation, keep my meaning and voice); the cleaned text is delivered so it lands in whatever text box I have focused in my browser (Claude, Gemini, etc.). This must feel instant. No spoken feedback here.

**Job B — Coaching (cold path):** Every utterance's raw transcript and cleaned version are logged. In dedicated practice sessions (and in a daily lesson), a local LLM finds my recurring mistakes, explains them, gives a native-idiomatic alternative, reads corrections back via TTS, and records the mistakes to a database. Daily, generate one or two focused mini-lessons from my most frequent recent error patterns.

These two jobs share components but run on different triggers. Do NOT put heavy correction/TTS/logging in the middle of the dictation hot path.

---

## 2. Hard constraints (do not violate)

- **Target:** Ubuntu 24.04 LTS, Intel Core Ultra 7, 32 GB RAM, NVIDIA RTX 5060 Ti 16 GB (Blackwell, sm_120). The GPU arrives in ~2 days — so **build CPU-first**: everything must run (slowly) on CPU now, with GPU selected via config/env. No hard dependency on CUDA being present at build time.
- **Blackwell/sm_120:** any container that uses PyTorch/CUDA MUST use CUDA 12.8+ base images and cu128 (or newer) PyTorch wheels, and PyTorch ≥ 2.7. Older cu124/cu126 wheels will crash with "no kernel image is available" on this GPU. Verify with a startup check that logs the detected compute capability.
- **Docker split — critical:** Containerize the *model servers only* (ASR, LLM, TTS), each exposing an HTTP API on localhost via docker-compose with GPU passthrough (NVIDIA Container Toolkit). The **host-integration client runs natively on the host in a uv-managed venv, NOT in a container** — it owns the microphone, speakers, global hotkey, and text injection. Containers talk model math; the host client talks to the OS. Do not try to pass audio devices or input injection through Docker.
- **Wayland text injection:** the session is Wayland (confirm with `echo $XDG_SESSION_TYPE`). `xdotool` will not work. Implement the injection layer behind an interface with two backends: (1) clipboard-paste via `wl-clipboard` (copy text, user presses Ctrl+V) as the safe default, and (2) `ydotool` auto-type. Make the backend configurable.
- **No pronunciation scoring in v1.** Pronunciation feedback from ASR text is not reliable (ASR normalizes to standard spelling and is accent-robust, so it masks mispronunciation). Scope grammar / word-choice / fluency / naturalness only. Leave a clean extension point (a `PronunciationScorer` interface) for a future v2 that would use a phoneme/forced-alignment model.

---

## 3. Recommended components (swap only with reason, log the reason)

- **ASR service:** `faster-whisper` (CTranslate2) serving an OpenAI-compatible `/v1/audio/transcriptions` endpoint. Default model `distil-large-v3` (fast) with `large-v3` as a config option. Use Silero VAD for endpointing on the client side.
- **LLM service:** Ollama (OpenAI-compatible `/v1`). Default model `qwen3:14b` (strong instruction-following at 16 GB); allow `gpt-oss:20b` or `gemma3:12b` via config. For the dictation hot path, use a small/fast model or disable "thinking" for latency; the coaching path may use the larger config.
- **TTS service:** Kokoro-82M behind a small FastAPI `/v1/audio/speech` endpoint (Apache-2.0, runs on CPU or ~2–3 GB VRAM, faster-than-real-time, clean native US/UK English — voice/accent from config). Piper as a fallback backend behind the same interface.
- **Host client:** Python (uv venv). `sounddevice`/`pyaudio` for mic + playback, `pynput` or a Wayland-compatible global-hotkey mechanism for push-to-talk, plus the injection layer above.

All three model services must be individually swappable because they sit behind clean HTTP interfaces.

---

## 4. Suggested repo layout

```
speakcoach/
  docker-compose.yml            # asr, llm(ollama), tts services; GPU passthrough; CUDA 12.8+ images
  .env.example                  # model names, device (cpu/cuda), voice, hotkey, injection backend
  services/
    asr/                        # faster-whisper server (Dockerfile pins cu128 / torch>=2.7)
    tts/                        # Kokoro FastAPI server (Dockerfile)
    # llm uses the official Ollama image; models pulled via entrypoint
  host_client/                  # runs natively via uv, NOT dockerized
    pyproject.toml
    speakcoach/
      audio.py                  # mic capture, VAD, playback
      asr_client.py tts_client.py llm_client.py   # thin HTTP clients
      dictation.py              # hot path: capture -> asr -> light clean -> inject
      coaching.py               # cold path: analyze, explain, TTS read-back, log
      inject.py                 # ClipboardBackend + YdotoolBackend behind one interface
      hotkey.py                 # push-to-talk + mode toggle
      lessons.py                # daily lesson generation from error stats
      db.py                     # SQLite access
      pronunciation.py          # PronunciationScorer interface, v1 = no-op stub
      config.py main.py
  scripts/
    healthcheck.py              # logs detected GPU compute capability + model reachability
    install_host.sh             # host prereqs reminder (does not sudo silently)
  systemd/
    speakcoach.service          # host client, always-on
    speakcoach-lesson.timer     # daily lesson job
  README.md
```

---

## 5. Data model (SQLite)

```sql
CREATE TABLE utterance (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  mode TEXT NOT NULL,           -- 'dictation' | 'practice'
  raw_transcript TEXT NOT NULL, -- straight from ASR
  cleaned_text TEXT,            -- what was injected / the correction target
  audio_path TEXT               -- optional retained wav for future pronunciation v2
);
CREATE TABLE mistake (
  id INTEGER PRIMARY KEY,
  utterance_id INTEGER REFERENCES utterance(id),
  category TEXT NOT NULL,       -- e.g. article, tense, preposition, word_choice, agreement, fluency
  original TEXT NOT NULL,
  correction TEXT NOT NULL,
  explanation TEXT,
  severity INTEGER              -- 1..3
);
CREATE TABLE lesson (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  topics TEXT NOT NULL,         -- JSON: the 1-2 error patterns targeted
  content TEXT NOT NULL         -- generated mini-lesson + practice prompts
);
```

The coaching LLM must return mistakes as structured JSON (category, original, correction, explanation, severity) so they insert cleanly. Prompt it to output JSON only, and parse defensively.

---

## 6. Build order (milestones — get me something usable fast)

1. **Skeleton + healthcheck.** Repo, docker-compose, `.env`, `healthcheck.py` that reports CPU/GPU and pings each service. No models yet.
2. **TTS service** (easiest to verify): Kokoro server + a CLI that speaks a sentence.
3. **ASR service** + host `audio.py`: press hotkey, speak, see raw transcript in terminal.
4. **Dictation hot path (Job A):** add light-cleanup LLM call + injection (clipboard backend first). End-to-end: speak → cleaned text on clipboard → I paste into a browser box. This is the first thing I actually use daily.
5. **Logging:** persist every utterance.
6. **Coaching path (Job B):** practice mode that analyzes, explains, reads back via TTS, and writes `mistake` rows.
7. **Daily lesson:** `lessons.py` + systemd timer that builds 1–2 mini-lessons from recent frequent errors.
8. **GPU flip:** once the card is in, switch `.env` device to cuda, confirm sm_120 via healthcheck, benchmark latency, tune model sizes.
9. **ydotool injection backend** and always-on systemd service.

Keep each milestone independently runnable and testable. Prefer OpenAI-compatible endpoints throughout so components stay swappable.

---

## 7. Acceptance checks

- CPU-only cold start works today; every service reports healthy.
- Dictation round-trip (speak → cleaned text available to paste) works and, on GPU, feels near-instant (target < ~1.5 s after I stop speaking).
- Light cleanup preserves my meaning; it does not silently rewrite me into different content.
- Coaching produces valid structured mistakes that land in SQLite, and a spoken read-back of the correction.
- Daily timer generates a lesson file/record from real logged errors.
- Nothing in the hot path blocks on TTS or the mistake logger.

---

## 8. Ask me before building (do not assume)

1. Primary priority: dictation-first, tutoring-first, or equal? (I lean dictation-first.)
2. Trigger: push-to-talk hotkey vs always-on VAD vs wake word? (I lean push-to-talk for dictation.)
3. Injection default: clipboard-paste or ydotool auto-type? (Clipboard for v1 unless I say otherwise.)
4. Correction aggressiveness: minimal fixes vs fuller native-idiomatic rewrite? (Minimal, with a separate "native alternative" line.)
5. TTS accent: US or UK English?
6. My `echo $XDG_SESSION_TYPE` and `nvidia-smi` (once the card is in) output.
7. Which LLM to start with: qwen3:14b, gpt-oss:20b, or gemma3:12b?

Start by confirming the plan and asking these, then scaffold milestone 1.
