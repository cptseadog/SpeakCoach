"""Push-to-talk hotkey + mode toggle (Wayland-compatible mechanism). Milestone 3."""

from collections.abc import Callable

from .config import Config


def listen(config: Config, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
    raise NotImplementedError("hotkey listener arrives in Milestone 3")
