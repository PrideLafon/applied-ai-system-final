"""Optional LLM client. The whole system also runs fully offline."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("vibefinder.llm")


class LLMError(RuntimeError):
    """Raised when the LLM call fails; callers fall back to offline logic."""


class GeminiLLM:
    """Minimal Gemini REST client (no SDK needed, only `requests`).

    Configure with the GEMINI_API_KEY environment variable. The model can
    be changed with GEMINI_MODEL.
    """

    def __init__(self, api_key: str, model: str, timeout: int = 20) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = f"gemini:{model}"

    def complete(self, prompt: str) -> str:
        """Send a prompt and return the text reply, or raise LLMError."""
        try:
            import requests  # imported lazily so offline mode needs nothing

            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{self.model}:generateContent")
            body = {"contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2}}
            resp = requests.post(url, json=body, timeout=self.timeout,
                                 headers={"x-goog-api-key": self.api_key})
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as err:  # network, quota, bad JSON, missing keys
            raise LLMError(f"Gemini call failed: {err}") from err


def get_llm() -> Optional[GeminiLLM]:
    """Return an LLM client if configured, else None (offline mode)."""
    if os.getenv("VIBEFINDER_OFFLINE", "").lower() in ("1", "true", "yes"):
        return None
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    return GeminiLLM(key, os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))