#!/usr/bin/env python3
"""System + service healthcheck. Stdlib only — runs with any Python 3.9+.

Reports host facts (session type, CPU, RAM, GPU compute capability) and pings
each model service. Exit code 0 only if every service responds.
"""

import json
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict:
    env = {}
    for name in (".env", ".env.example"):
        path = REPO_ROOT / name
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env[key.strip()] = value.split("#")[0].strip()
            break
    env.update({k: v for k, v in os.environ.items() if k in env})
    return env


def mem_total_gb() -> str:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return f"{int(line.split()[1]) / 1024 / 1024:.1f} GB"
    except OSError:
        pass
    return "unknown"


def gpu_report(device: str) -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "none detected (expected — CPU-first until the card arrives)"
    if out.returncode != 0:
        return f"nvidia-smi error: {out.stderr.strip() or out.stdout.strip()}"
    gpus = out.stdout.strip()
    if device == "cpu":
        return f"{gpus}  [WARNING: GPU present but DEVICE=cpu — flip .env for Milestone 8]"
    return gpus


def ping(name: str, url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode()
        try:
            detail = json.dumps(json.loads(body))
        except json.JSONDecodeError:
            detail = body[:120]
        return True, detail
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return False, str(e)


def main() -> int:
    env = load_env()
    device = env.get("DEVICE", "cpu")

    print("== SpeakCoach healthcheck ==")
    print(f"host:        {platform.platform()}")
    print(f"session:     {os.environ.get('XDG_SESSION_TYPE', 'unknown')}")
    print(f"cpu:         {os.cpu_count()} cores")
    print(f"ram:         {mem_total_gb()}")
    print(f"device cfg:  {device}")
    print(f"gpu:         {gpu_report(device)}")
    print()

    checks = [
        ("asr", f"{env.get('ASR_URL', 'http://127.0.0.1:8001')}/health"),
        ("tts", f"{env.get('TTS_URL', 'http://127.0.0.1:8002')}/health"),
        ("llm", f"{env.get('LLM_URL', 'http://127.0.0.1:11434')}/api/version"),
    ]
    failed = False
    for name, url in checks:
        ok, detail = ping(name, url)
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {name:4} {url}\n       {detail}")
        failed |= not ok

    print()
    if failed:
        print("Some services are unreachable. Start them with: docker compose up -d")
        return 1
    print("All services healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
