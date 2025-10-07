#!/usr/bin/env python3
"""
Check session data and interactions for a specific session
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import app modules
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from app.core.database.session import get_transaction_context
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.user_session import UserSession
from sqlalchemy import select, and_
from app.core.logging import get_logger

logger = get_logger(__name__)


async def check_session_data(shop_id: str, session_id: str):
    """Check session data and interactions for a specific session"""

    print(f"🔍 Checking session data for shop_id: {shop_id}, session_id: {session_id}")

    async with get_transaction_context() as session:
        # 1. Check if session exists
        session_result = await session.execute(
            select(UserSession).where(
                and_(UserSession.shop_id == shop_id, UserSession.id == session_id)
            )
        )
        user_session = session_result.scalar_one_or_none()

        if not user_session:
            print(f"❌ Session {session_id} not found")
            return

        print(f"✅ Session found:")
        print(f"   - ID: {user_session.id}")
        print(f"   - Customer ID: {user_session.customer_id}")
        print(f"   - Client ID: {user_session.client_id}")
        print(f"   - Status: {user_session.status}")
        print(f"   - Created: {user_session.created_at}")
        print(f"   - Last Active: {user_session.last_active}")
        print(f"   - Total Interactions: {user_session.total_interactions}")
        print(f"   - Extensions Used: {user_session.extensions_used}")

        # 2. Check interactions for this session
        interactions_result = await session.execute(
            select(UserInteraction)
            .where(
                and_(
                    UserInteraction.shop_id == shop_id,
                    UserInteraction.session_id == session_id,
                )
            )
            .order_by(UserInteraction.created_at.desc())
        )
        interactions = interactions_result.scalars().all()

        print(f"\n📊 Found {len(interactions)} interactions for this session")

        if interactions:
            print("\n📋 Interaction Details:")
            for i, interaction in enumerate(interactions[:10]):  # Show first 10
                print(f"  {i+1}. Type: {interaction.interaction_type}")
                print(f"     Extension: {interaction.extension_type}")
                print(f"     Customer: {interaction.customer_id}")
                print(f"     Created: {interaction.created_at}")
                print(f"     Metadata: {interaction.interaction_metadata}")
                print()
        else:
            print("❌ No interactions found for this session")

            # Check if there are any interactions at all for this shop
            all_interactions_result = await session.execute(
                select(UserInteraction).where(UserInteraction.shop_id == shop_id)
            )
            all_interactions = all_interactions_result.scalars().all()
            print(f"📊 Total interactions in shop: {len(all_interactions)}")

            if all_interactions:
                print("🔍 Sample interactions in shop:")
                for i, interaction in enumerate(all_interactions[:3]):
                    print(
                        f"  {i+1}. Session: {interaction.session_id} | Type: {interaction.interaction_type} | Customer: {interaction.customer_id}"
                    )

        # 3. Check other sessions for this customer
        if user_session.customer_id:
            print(
                f"\n👤 Checking other sessions for customer {user_session.customer_id}"
            )
            customer_sessions_result = await session.execute(
                select(UserSession)
                .where(
                    and_(
                        UserSession.shop_id == shop_id,
                        UserSession.customer_id == user_session.customer_id,
                    )
                )
                .order_by(UserSession.created_at.desc())
            )
            customer_sessions = customer_sessions_result.scalars().all()

            print(f"📊 Found {len(customer_sessions)} sessions for this customer")
            for i, sess in enumerate(customer_sessions[:3]):
                print(
                    f"  {i+1}. Session: {sess.id} | Interactions: {sess.total_interactions} | Created: {sess.created_at}"
                )


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Check session data")
    parser.add_argument("--shop-id", required=True, help="Shop ID")
    parser.add_argument("--session-id", required=True, help="Session ID")

    args = parser.parse_args()

    await check_session_data(args.shop_id, args.session_id)


if __name__ == "__main__":
    asyncio.run(main())
