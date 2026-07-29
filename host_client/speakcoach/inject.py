"""Wayland text injection behind one interface.

xdotool does not work on Wayland. Two backends:
  - ClipboardBackend (wl-clipboard): copies text; the user presses Ctrl+V. Safe v1 default.
  - YdotoolBackend: auto-types via ydotool. Opt-in, Milestone 9.
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
    """Auto-types into the focused field. Needs the ydotoold user daemon with
    /dev/uinput access — see the README's "ydotool auto-type" section."""

    def __init__(self) -> None:
        if shutil.which("ydotool") is None:
            raise RuntimeError("ydotool not found — see README 'ydotool auto-type' for setup")

    def inject(self, text: str) -> str:
        proc = subprocess.run(
            ["ydotool", "type", "--", text], capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"ydotool failed: {proc.stderr.strip() or 'is the ydotoold daemon running?'}"
            )
        return "typed into the focused field"


def get_backend(config: Config) -> InjectionBackend:
    backends = {"clipboard": ClipboardBackend, "ydotool": YdotoolBackend}
    try:
        return backends[config.injection_backend]()
    except KeyError:
        raise ValueError(
            f"unknown INJECTION_BACKEND {config.injection_backend!r}; "
            f"expected one of {sorted(backends)}"
        ) from None
