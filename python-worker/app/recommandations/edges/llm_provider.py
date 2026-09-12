"""
Thin LLM provider interface for the enrichment pass.

Kept deliberately small — one method, strings in and out. The enrichment tier's
pricing and quality have shifted repeatedly, so swapping provider should be a
config change and not a refactor. Nothing above this module knows which model
answered, and nothing below it knows what the JSON means.
"""

import asyncio
import logging
import random
from typing import Optional, Protocol

from app.core.metrics import gen_ai_cost, gen_ai_token_usage

from .llm_budget import LLMBudget
from .llm_pricing import cost_usd, is_priced

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

    def __init__(
        self,
        api_key: str,
        model: str,
        retries: int = 2,
        timeout: int = 120,
        budget: Optional[LLMBudget] = None,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.api_key = api_key
        self.model = model
        self.retries = retries
        self.timeout = timeout
        # Circuit breaker + daily ceiling + error classification. Shared across
        # workers via Redis, so an outage is recognised once rather than
        # rediscovered by every shop's sweep.
        self.budget = budget or LLMBudget()
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _record_usage(self, response) -> None:
        """Record tokens and spend for one successful call.

        Recorded here rather than inferred from the prompt later: only the
        provider knows the real token count, and only this moment knows which
        model actually served the request.

        Telemetry must never be the reason a completion fails, so every branch
        is defensive — a provider that stops returning usage_metadata should
        cost us the metric, not the answer we already have in hand.
        """
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is None:
                return
            prompt = int(getattr(usage, "prompt_token_count", 0) or 0)
            # Gemini reports thinking tokens separately, and they are billed as
            # output. Leaving them out understates the cost of a reasoning model.
            output = int(getattr(usage, "candidates_token_count", 0) or 0) + int(
                getattr(usage, "thoughts_token_count", 0) or 0
            )

            base = {"gen_ai.system": "gcp.gemini", "gen_ai.request.model": self.model}
            gen_ai_token_usage.record(prompt, {**base, "gen_ai.token.type": "input"})
            gen_ai_token_usage.record(output, {**base, "gen_ai.token.type": "output"})

            if not is_priced(self.model):
                # Not an error, but it means the cost dashboard is undercounting
                # by however much this model is being used.
                logger.warning(
                    "No price entry for model %s; cost recorded as 0. "
                    "Add it to llm_pricing.PRICES.",
                    self.model,
                )
            gen_ai_cost.add(cost_usd(self.model, prompt, output), base)
        except Exception:
            logger.debug("LLM usage metric skipped", exc_info=True)

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

        # Checked once before the in-process retries, not per attempt: if the
        # circuit is open or the day's ceiling is spent, no amount of local
        # retrying is going to help.
        await self.budget.check()

        last_error = None
        for attempt in range(self.retries + 1):
            try:
                await self.budget.record_call()
                response = await asyncio.wait_for(
                    self._get_client().aio.models.generate_content(
                        model=self.model, contents=user, config=config
                    ),
                    timeout=self.timeout,
                )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("empty response from model")
                await self.budget.record_success()
                self._record_usage(response)
                return text
            except Exception as e:
                last_error = e
                classification = await self.budget.record_failure(e)

                # A permanent error will fail identically next time. Retrying
                # it locally, and then again from the sweeper, is pure spend.
                if not classification.retryable:
                    raise RuntimeError(
                        f"{self.model} failed permanently "
                        f"({classification.reason}): {e}"
                    ) from e

                if attempt < self.retries:
                    # Jitter so every shop's sweep does not retry in lockstep
                    # and re-hit a rate limit together.
                    delay = (2**attempt) * (1 + random.random() * 0.3)
                    await asyncio.sleep(delay)

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
    """Construct the configured provider from app settings.

    The AI fields live on the `ml` sub-model, not on Settings itself. Reading
    them off the root object returned the "" default via getattr, so every
    enrichment run raised "GEMINI_API_KEY is not set" no matter what was in the
    environment. Accepts either shape so a bare MLSettings also works in tests.
    """
    ai = getattr(settings, "ml", settings)
    return GeminiProvider(
        api_key=getattr(ai, "GEMINI_API_KEY", "") or "",
        model=getattr(ai, "AI_CHAT_MODEL", "gemini-2.5-flash-lite"),
    )
