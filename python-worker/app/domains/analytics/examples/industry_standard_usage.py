"""
Industry Standard Usage Examples

Examples showing how to use the industry-standard customer identity resolution
and cross-session linking system.
"""

import asyncio
from datetime import datetime, timedelta

from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.services.customer_identity_resolution_service import (
    CustomerIdentityResolutionService,
)
from app.domains.analytics.services.cross_session_linking_service import (
    CrossSessionLinkingService,
)
from app.domains.analytics.models.extension import ExtensionType, ExtensionContext
from app.domains.analytics.models.interaction import InteractionType


class IndustryStandardAnalyticsExample:
    """Example of industry-standard analytics implementation"""

    def __init__(self):
        self.session_service = UnifiedSessionService()
        self.identity_resolution_service = CustomerIdentityResolutionService()
        self.cross_session_linking_service = CrossSessionLinkingService()

    async def example_48_hour_customer_journey(self):
        """
        Example: 48-hour customer journey with industry-standard linking

        This demonstrates how the system handles a customer who:
        1. Visits anonymously on Day 1
        2. Returns and purchases on Day 3
        3. Gets linked across sessions
        """
        print("=== 48-Hour Customer Journey Example ===")

        shop_id = "example-shop.myshopify.com"
        customer_id = "customer_123"

        # Day 1: Anonymous user visits
        print("\nDay 1: Anonymous user visits...")

        anonymous_session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=None,  # Anonymous
            browser_session_id="browser_abc123",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            ip_address="192.168.1.100",
        )

        print(f"Created anonymous session: {anonymous_session.id}")
        print(f"Session expires in: {anonymous_session.expires_at}")

        # Simulate some interactions
        await self._simulate_anonymous_interactions(anonymous_session.id, shop_id)

        # Day 3: Same user returns and purchases
        print("\nDay 3: Same user returns and purchases...")

        # Create new session (simulating return visit)
        purchase_session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=None,  # Still anonymous initially
            browser_session_id="browser_abc123",  # Same browser session
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",  # Same UA
            ip_address="192.168.1.100",  # Same IP
        )

        print(f"Created purchase session: {purchase_session.id}")

        # Simulate purchase interaction
        await self._simulate_purchase_interaction(purchase_session.id, shop_id)

        # Customer identifies (login or purchase completion)
        print("\nCustomer identifies...")

        identification_result = (
            await self.identity_resolution_service.resolve_customer_identity(
                customer_id=customer_id,
                current_session_id=purchase_session.id,
                shop_id=shop_id,
                customer_data={"email": "customer@example.com", "phone": "+1234567890"},
            )
        )

        print(f"Identity resolution result: {identification_result}")

        # Cross-session linking
        print("\nPerforming cross-session linking...")

        linking_result = (
            await self.cross_session_linking_service.link_customer_sessions(
                customer_id=customer_id,
                shop_id=shop_id,
                trigger_session_id=purchase_session.id,
            )
        )

        print(f"Cross-session linking result: {linking_result}")

        # Get complete customer journey
        print("\nComplete customer journey:")

        customer_sessions = await self.session_service.query_sessions(
            self.session_service.SessionQuery(customer_id=customer_id, shop_id=shop_id)
        )

        print(f"Total sessions linked: {len(customer_sessions)}")
        for session in customer_sessions:
            print(
                f"  - Session {session.id}: {session.total_interactions} interactions, "
                f"extensions: {session.extensions_used}"
            )

        return {
            "anonymous_session": anonymous_session.id,
            "purchase_session": purchase_session.id,
            "total_sessions": len(customer_sessions),
            "identification_result": identification_result,
            "linking_result": linking_result,
        }

    async def example_cross_device_journey(self):
        """
        Example: Cross-device customer journey

        This demonstrates how the system handles a customer who:
        1. Visits on desktop (anonymous)
        2. Visits on mobile (anonymous)
        3. Purchases on desktop (identified)
        4. Gets linked across devices
        """
        print("\n=== Cross-Device Customer Journey Example ===")

        shop_id = "example-shop.myshopify.com"
        customer_id = "customer_456"

        # Desktop visit (anonymous)
        print("\nDesktop visit (anonymous)...")

        desktop_session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=None,
            browser_session_id="desktop_browser_123",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            ip_address="192.168.1.100",  # Home IP
        )

        await self._simulate_anonymous_interactions(desktop_session.id, shop_id)

        # Mobile visit (anonymous, same IP)
        print("\nMobile visit (anonymous, same IP)...")

        mobile_session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=None,
            browser_session_id="mobile_browser_456",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            ip_address="192.168.1.100",  # Same home IP
        )

        await self._simulate_anonymous_interactions(mobile_session.id, shop_id)

        # Desktop purchase (identified)
        print("\nDesktop purchase (identified)...")

        purchase_session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=None,  # Anonymous initially
            browser_session_id="desktop_browser_123",  # Same desktop browser
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            ip_address="192.168.1.100",  # Same home IP
        )

        await self._simulate_purchase_interaction(purchase_session.id, shop_id)

        # Customer identifies
        print("\nCustomer identifies...")

        identification_result = (
            await self.identity_resolution_service.resolve_customer_identity(
                customer_id=customer_id,
                current_session_id=purchase_session.id,
                shop_id=shop_id,
                customer_data={"email": "customer456@example.com"},
            )
        )

        print(f"Identity resolution result: {identification_result}")

        # Cross-session linking should link mobile session via IP
        linking_result = (
            await self.cross_session_linking_service.link_customer_sessions(
                customer_id=customer_id,
                shop_id=shop_id,
                trigger_session_id=purchase_session.id,
            )
        )

        print(f"Cross-session linking result: {linking_result}")

        return {
            "desktop_session": desktop_session.id,
            "mobile_session": mobile_session.id,
            "purchase_session": purchase_session.id,
            "identification_result": identification_result,
            "linking_result": linking_result,
        }

    async def _simulate_anonymous_interactions(self, session_id: str, shop_id: str):
        """Simulate anonymous user interactions"""
        from app.domains.analytics.services.analytics_tracking_service import (
            AnalyticsTrackingService,
        )

        analytics_service = AnalyticsTrackingService()

        # Simulate page views
        await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=ExtensionContext.HOMEPAGE,
            interaction_type=InteractionType.PAGE_VIEW,
            shop_id=shop_id,
        )

        await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=ExtensionContext.PRODUCT_PAGE,
            interaction_type=InteractionType.PRODUCT_VIEW,
            shop_id=shop_id,
            product_id="product_123",
        )

        await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=ExtensionContext.PRODUCT_PAGE,
            interaction_type=InteractionType.CLICK,
            shop_id=shop_id,
            product_id="product_123",
        )

    async def _simulate_purchase_interaction(self, session_id: str, shop_id: str):
        """Simulate purchase interaction"""
        from app.domains.analytics.services.analytics_tracking_service import (
            AnalyticsTrackingService,
        )

        analytics_service = AnalyticsTrackingService()

        # Simulate cart interactions
        await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=ExtensionContext.CART_PAGE,
            interaction_type=InteractionType.CART_VIEW,
            shop_id=shop_id,
        )

        await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=ExtensionContext.CART_PAGE,
            interaction_type=InteractionType.RECOMMENDATION_CLICK,
            shop_id=shop_id,
            product_id="product_456",
            recommendation_id="rec_123",
            recommendation_position=1,
        )

        # Simulate purchase
        await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.RECOMMENDATION_PURCHASE,
            shop_id=shop_id,
            product_id="product_456",
            value=29.99,
        )


async def run_examples():
    """Run all examples"""
    example = IndustryStandardAnalyticsExample()

    # Run 48-hour journey example
    result1 = await example.example_48_hour_customer_journey()

    # Run cross-device journey example
    result2 = await example.example_cross_device_journey()

    print("\n=== Summary ===")
    print(f"48-hour journey: {result1['total_sessions']} sessions linked")
    print(
        f"Cross-device journey: {result2['linking_result']['total_sessions']} sessions linked"
    )

    return result1, result2


if __name__ == "__main__":
    # Run examples
    asyncio.run(run_examples())
