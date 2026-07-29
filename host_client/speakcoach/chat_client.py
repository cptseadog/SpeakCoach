"""Chat client for any OpenAI-compatible API (OpenAI, OpenRouter, DeepSeek, ...).

Configured via CHAT_API_BASE_URL / CHAT_API_KEY / CHAT_API_MODEL in .env.
Presents the same `send(messages) -> str` shape as the local client wrapper in
chat.py, so the chat loop doesn't care which backend it's talking to.
"""

import httpx

from .config import Config


class ApiChatClient:
    def __init__(self, config: Config, model: str | None = None):
        if not config.chat_api_base_url:
            raise RuntimeError("CHAT_API_BASE_URL is not set in .env (e.g. https://api.openai.com/v1)")
        if not config.chat_api_key:
            raise RuntimeError("CHAT_API_KEY is not set in .env")
        self.model = model or config.chat_api_model
        if not self.model:
            raise RuntimeError("CHAT_API_MODEL is not set in .env (and no --model given)")
        self.base_url = config.chat_api_base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {config.chat_api_key}"}

    def send(self, messages: list[dict]) -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers,
            json={"model": self.model, "messages": messages},
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        if resp.status_code != 200:
            raise RuntimeError(f"chat API error ({resp.status_code}): {resp.text[:300]}")
        try:
            reply = resp.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise RuntimeError(f"unexpected chat API response shape: {e}") from None
        if not reply:
            raise RuntimeError("chat API returned an empty reply")
        return reply
