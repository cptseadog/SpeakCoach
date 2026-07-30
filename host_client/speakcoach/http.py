"""Shared HTTP POST wrapper.

The model servers live in containers that may simply be stopped
(RESTART_POLICY=no — see scripts/preheat.sh), so "connection refused" is an
expected, recoverable state. Turn transport failures into RuntimeErrors whose
message says what to do, instead of an httpx traceback.
"""

import httpx

PREHEAT_HINT = "start the services with ./scripts/preheat.sh"


def post(service: str, url: str, hint: str = PREHEAT_HINT, **kwargs) -> httpx.Response:
    try:
        return httpx.post(url, **kwargs)
    except httpx.ConnectError:
        raise RuntimeError(f"cannot reach the {service} service at {url} — {hint}") from None
    except httpx.TimeoutException as e:
        raise RuntimeError(f"the {service} service timed out ({type(e).__name__})") from None
    except httpx.HTTPError as e:
        raise RuntimeError(f"{service} request failed: {type(e).__name__}: {e}") from None
