"""
LLM enrichment layer using Vertex AI Gemini.

Generates:
1. Natural language explanations for recommendations ("Why this?")
2. Context-aware section titles
3. Product descriptions for recommendation cards
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class LLMEnricher:
    """Enriches recommendations with LLM-generated content via Vertex AI Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash-001",
    ):
        self.api_key = api_key or os.getenv("VERTEX_AI_API_KEY")
        self.model_name = model_name
        self._client = None
        self._enabled = bool(self.api_key)

    async def _ensure_client(self):
        """Lazy-init Gemini client."""
        if self._client is not None:
            return self._client
        if not self._enabled:
            return None

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
            logger.info(f"✅ Gemini initialized: {self.model_name}")
            return self._client
        except Exception as e:
            logger.error(f"Failed to init Gemini: {e}")
            self._enabled = False
            return None

    async def enrich_recommendations(
        self,
        context: str,
        user_context: Optional[Dict[str, Any]],
        recommended: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Add LLM-generated explanations to recommended products.

        Args:
            context: Recommendation context (checkout, post_purchase, account).
            user_context: User/cart info for personalized explanations.
            recommended: List of recommended product dicts.

        Returns:
            Same list with added 'explanation' and 'section_title' fields.
        """
        if not self._enabled or not recommended:
            return recommended

        client = await self._ensure_client()
        if client is None:
            return recommended

        try:
            prompt = self._build_enrichment_prompt(context, user_context, recommended)
            response = client.generate_content(prompt)
            enriched = self._parse_response(response.text, recommended)
            return enriched
        except Exception as e:
            logger.warning(f"LLM enrichment failed (non-blocking): {e}")
            return recommended

    async def generate_section_title(
        self,
        context: str,
        user_context: Optional[Dict[str, Any]],
        products: List[Dict[str, Any]],
    ) -> str:
        """Generate a context-aware section title.

        Example outputs:
        - "Complete Your Running Kit"
        - "Based on Your Recent Purchase"
        - "You Might Also Like"
        - "Frequently Bought Together"
        """
        if not self._enabled or not products:
            return self._default_title(context)

        client = await self._ensure_client()
        if client is None:
            return self._default_title(context)

        try:
            titles = [p.get("title", "") for p in products[:3]]
            prompt = f"""
            Context: {context}
            Recommended products: {', '.join(titles)}

            Generate a short, compelling section title (max 5 words) for these recommendations.
            Make it context-aware. Examples: "Complete Your Look", "You Might Also Like",
            "Frequently Bought Together", "Based on Your Cart".
            Return ONLY the title, nothing else.
            """
            response = client.generate_content(prompt)
            title = response.text.strip().strip('"').strip("'")
            return title[:60] if title else self._default_title(context)
        except Exception:
            return self._default_title(context)

    def _build_enrichment_prompt(
        self,
        context: str,
        user_context: Optional[Dict[str, Any]],
        recommended: List[Dict[str, Any]],
    ) -> str:
        """Build the prompt for recommendation explanations."""
        products_json = json.dumps(
            [
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "price": p.get("price"),
                    "type": p.get("product_type"),
                    "vendor": p.get("vendor"),
                }
                for p in recommended
            ],
            indent=2,
        )

        user_info = ""
        if user_context:
            user_info = f"""
            User context:
            - Cart items: {user_context.get('cart_items', [])}
            - Recent purchases: {user_context.get('recent_purchases', [])}
            - Context: {user_context.get('context', context)}
            """

        return f"""
        You are a recommendations explainer for an e-commerce AI app.

        Context: {context}
        {user_info}

        Recommended products:
        {products_json}

        For each recommended product, generate:
        1. "explanation": A 1-sentence natural language explanation of why this product
           is recommended (e.g., "Pairs well with the jeans in your cart")
        2. "section_title": A short, context-appropriate section title

        Return a JSON array with objects containing: product_id, explanation, section_title.
        Keep explanations short (10-20 words). Be specific, not generic.
        Return ONLY valid JSON, no markdown formatting.
        """

    def _parse_response(
        self,
        response_text: str,
        recommended: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Parse Gemini response and merge with recommendations."""
        try:
            # Clean markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("\n", 1)[0]
            if text.endswith("```"):
                text = text[:-3]

            explanations = json.loads(text)
            expl_map = {
                e.get("product_id"): e for e in explanations if "product_id" in e
            }

            for product in recommended:
                pid = product.get("id")
                if pid in expl_map:
                    product["explanation"] = expl_map[pid].get("explanation", "")
                    if "section_title" in expl_map[pid]:
                        product["section_title"] = expl_map[pid]["section_title"]

            return recommended
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return recommended

    @staticmethod
    def _default_title(context: str) -> str:
        """Fallback titles when LLM is unavailable."""
        titles = {
            "checkout": "Complete Your Order",
            "post_purchase": "Complete Your Look",
            "cart": "You Might Also Like",
            "product_page": "Complete the Set",
            "homepage": "Recommended for You",
            "collection_page": "You Might Also Like",
            "profile": "Based on Your Style",
            "order_status": "Complete Your Outfit",
            "order_history": "Based on Your Orders",
        }
        return titles.get(context, "Recommended for You")
