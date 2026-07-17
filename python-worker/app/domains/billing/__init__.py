"""
Billing Domain Package

Attribution computation lives here (attribution_engine.py). Actual billing
(Shopify subscription creation/webhooks) is handled in the Remix app, which
has direct authenticated access to Shopify's Admin GraphQL API per-request.
"""
