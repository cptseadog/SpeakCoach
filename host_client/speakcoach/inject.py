"""Wayland text injection behind one interface.

xdotool does not work on Wayland. Two backends:
  - ClipboardBackend (wl-clipboard): copies text; the user presses Ctrl+V.
    The default, and the only one the project requires.
  - YdotoolBackend: auto-types via ydotool. Fully optional — it needs a package,
    a daemon, and /dev/uinput group access that a normal desktop does not grant.
    Selecting it when it isn't usable degrades to the clipboard instead of
    failing: a text-delivery preference must never cost the user an utterance.
"""

import shutil
import subprocess
from abc import ABC, abstractmethod

from .config import Config


class InjectionBackend(ABC):
    @abstractmethod
    def inject(self, text: str) -> str:
        """Deliver text toward the focused text box. Returns a short human note
        telling the user what to do next (e.g. 'press Ctrl+V')."""


class ClipboardBackend(InjectionBackend):
    def __init__(self) -> None:
        if shutil.which("wl-copy") is None:
            raise RuntimeError("wl-copy not found — install wl-clipboard (see scripts/install_host.sh)")

    def inject(self, text: str) -> str:
        subprocess.run(["wl-copy", "--", text], check=True, timeout=5)
        return "copied — press Ctrl+V to paste"


class YdotoolBackend(InjectionBackend):
    """Auto-types into the focused field. Optional: needs the ydotool package and
    the ydotoold user daemon with /dev/uinput access — see the README's "ydotool
    auto-type (optional)" section. `fallback` receives the text if ydotool fails
    at runtime (daemon not running is the common case), so the transcript
    survives a broken auto-type setup."""

    def __init__(self, fallback: InjectionBackend | None = None) -> None:
        if shutil.which("ydotool") is None:
            raise RuntimeError(
                "ydotool not installed — it is optional; see README 'ydotool auto-type'"
            )
        self._fallback = fallback

    def inject(self, text: str) -> str:
        try:
            proc = subprocess.run(
                ["ydotool", "type", "--", text], capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return "typed into the focused field"
            reason = proc.stderr.strip() or "is the ydotoold daemon running?"
        except (OSError, subprocess.TimeoutExpired) as e:
            reason = str(e)
        if self._fallback is None:
            raise RuntimeError(f"ydotool failed: {reason}")
        return f"ydotool failed ({reason}) — {self._fallback.inject(text)}"


def get_backend(config: Config) -> InjectionBackend:
    """Clipboard is the default. An unusable ydotool warns and degrades to it."""
    if config.injection_backend == "clipboard":
        return ClipboardBackend()
    if config.injection_backend != "ydotool":
        raise ValueError(
            f"unknown INJECTION_BACKEND {config.injection_backend!r}; "
            f"expected one of ['clipboard', 'ydotool']"
        )
    clipboard = ClipboardBackend()
    try:
        return YdotoolBackend(fallback=clipboard)
    except RuntimeError as e:
        print(f"warning: {e}\n         using the clipboard backend instead")
        return clipboard
