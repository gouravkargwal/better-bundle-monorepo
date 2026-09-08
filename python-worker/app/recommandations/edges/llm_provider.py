"""
Thin LLM provider interface for the enrichment pass.

Kept deliberately small — one method, strings in and out. The enrichment tier's
pricing and quality have shifted repeatedly, so swapping provider should be a
config change and not a refactor. Nothing above this module knows which model
answered, and nothing below it knows what the JSON means.
"""

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Anything that can answer a prompt with text."""

    async def complete(self, system: str, user: str) -> str:  # pragma: no cover
        ...


class GeminiProvider:
    """Google AI Studio (Gemini) provider.

    Retries with exponential backoff and raises on final failure. It must raise
    rather than return a placeholder: a silently empty enrichment would write
    zero priors for a whole batch and the shop would look cold on install day
    with nothing in the logs to explain why.
    """

    def __init__(self, api_key: str, model: str, retries: int = 2, timeout: int = 120):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.model = model
        self.retries = retries
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def complete(self, system: str, user: str) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            # The enrichment schema is JSON; asking for it directly avoids
            # having to strip markdown fences from every response.
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = await asyncio.wait_for(
                    self._get_client().aio.models.generate_content(
                        model=self.model, contents=user, config=config
                    ),
                    timeout=self.timeout,
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("empty response from model")
                return text
            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    await asyncio.sleep(2**attempt)

        raise RuntimeError(
            f"{self.model} failed after {self.retries + 1} attempts: {last_error}"
        ) from last_error


class StaticProvider:
    """Returns canned responses. For tests and for dry-running the pipeline."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        if not self._responses:
            raise RuntimeError("StaticProvider ran out of responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def build_provider(settings) -> LLMProvider:
    """Construct the configured provider from app settings."""
    return GeminiProvider(
        api_key=getattr(settings, "GEMINI_API_KEY", "") or "",
        model=getattr(settings, "AI_CHAT_MODEL", "gemini-2.5-flash-lite"),
    )
