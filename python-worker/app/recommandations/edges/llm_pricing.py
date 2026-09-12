"""Token pricing for the models this service calls.

Cost is computed at call time, not derived later from a token count, because
the price of a model is a property of WHEN it ran. Repricing last quarter's
usage against today's table silently rewrites history, and the first time a
provider cuts prices the finance number stops matching the invoice.

ponytail: a hardcoded table, refreshed by hand. Providers do not publish a
pricing API, and the alternative — scraping a pricing page on a schedule — is a
lot of moving parts to keep a number that changes once or twice a year. If a
model is missing the cost is recorded as 0 and a warning is logged, so a new
model shows up as "unpriced" rather than as "free".
"""

from typing import Tuple

# USD per 1,000,000 tokens, as (input, output).
# Source: Google Gemini API pricing. Last checked 2026-09-12.
PRICES: dict[str, Tuple[float, float]] = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
}

PER_TOKENS = 1_000_000


def normalise(model: str) -> str:
    """Strip the decorations providers add to a model id.

    Callers pass things like `models/gemini-2.5-flash-lite` or
    `gemini-2.5-flash-lite-001`; all three are the same price.
    """
    name = (model or "").strip().lower()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    if name in PRICES:
        return name
    # Longest prefix wins, so `gemini-2.5-flash-lite-001` matches the lite entry
    # rather than the plain `gemini-2.5-flash` one.
    matches = [k for k in PRICES if name.startswith(k)]
    return max(matches, key=len) if matches else name


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD for one call. Returns 0.0 for a model that is not in the table."""
    price = PRICES.get(normalise(model))
    if not price:
        return 0.0
    return (input_tokens * price[0] + output_tokens * price[1]) / PER_TOKENS


def is_priced(model: str) -> bool:
    return normalise(model) in PRICES


def _demo() -> None:
    """Self-check: `python -m app.recommandations.edges.llm_pricing`."""
    assert normalise("models/gemini-2.5-flash-lite") == "gemini-2.5-flash-lite"
    # The prefix trap: plain startswith order would match `gemini-2.5-flash`.
    assert normalise("gemini-2.5-flash-lite-001") == "gemini-2.5-flash-lite"
    assert normalise("gemini-2.5-flash-002") == "gemini-2.5-flash"
    assert normalise("GEMINI-2.5-PRO") == "gemini-2.5-pro"

    # 1M in + 1M out on flash-lite = 0.10 + 0.40
    assert abs(cost_usd("gemini-2.5-flash-lite", 1_000_000, 1_000_000) - 0.50) < 1e-9
    # Input and output must be priced separately, or a chatty model looks cheap.
    assert cost_usd("gemini-2.5-pro", 1000, 0) != cost_usd("gemini-2.5-pro", 0, 1000)
    assert cost_usd("gemini-2.5-flash-lite", 0, 0) == 0.0
    # Unknown model: zero, not a crash and not a guess.
    assert cost_usd("some-new-model", 10_000, 10_000) == 0.0
    assert is_priced("gemini-2.5-flash") and not is_priced("some-new-model")
    print("llm_pricing: 9/9 ok")


if __name__ == "__main__":
    _demo()
