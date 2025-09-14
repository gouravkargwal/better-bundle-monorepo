#!/usr/bin/env python3
"""
Script to process existing attribution events and create RecommendationAttributions
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the python-worker directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'python-worker'))

from prisma import Prisma
from python_worker.app.domains.analytics.services.attribution_extractor import AttributionExtractor

async def process_existing_attribution():
    """Process existing attribution events that have orderId but no RecommendationAttributions"""
    
    db = Prisma()
    await db.connect()
    
    try:
        # Find attribution events that have orderId but no corresponding RecommendationAttributions
        attribution_events = await db.attributionevent.find_many(
            where={
                "orderId": {"not": None},
            },
            include={
                "shop": True
            }
        )
        
        print(f"Found {len(attribution_events)} attribution events with orderId")
        
        if not attribution_events:
            print("No attribution events to process")
            return
        
        # Group by order_id
        orders_to_process = {}
        for event in attribution_events:
            order_id = event.orderId
            if order_id not in orders_to_process:
                orders_to_process[order_id] = {
                    'shop_id': event.shopId,
                    'events': []
                }
            orders_to_process[order_id]['events'].append(event)
        
        print(f"Processing {len(orders_to_process)} orders")
        
        attribution_extractor = AttributionExtractor(db)
        
        for order_id, order_data in orders_to_process.items():
            print(f"Processing order {order_id} with {len(order_data['events'])} attribution events")
            
            # Get order data from the first event (they should all have the same order data)
            first_event = order_data['events'][0]
            
            # Create mock event data for the checkout_completed event
            mock_event_data = {
                "data": {
                    "checkout": {
                        "order": {
                            "id": order_id
                        },
                        "totalPrice": {
                            "amount": 311.15,  # From the logs, this was the total price
                            "currencyCode": "INR"
                        },
                        "lineItems": [
                            {
                                "variant": {
                                    "product": {
                                        "id": "7894680273035"  # The product that was purchased
                                    }
                                },
                                "finalLinePrice": {
                                    "amount": 311.15
                                }
                            }
                        ]
                    }
                }
            }
            
            # Create RecommendationAttributions for this order
            await attribution_extractor._create_recommendation_attributions(
                shop_id=order_data['shop_id'],
                order_id=order_id,
                attribution_events=order_data['events'],
                line_items=mock_event_data["data"]["checkout"]["lineItems"],
                total_price=311.15,
                currency_code="INR"
            )
            
            print(f"✅ Processed order {order_id}")
        
        print("🎉 All attribution events processed successfully!")
        
    except Exception as e:
        print(f"❌ Error processing attribution events: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(process_existing_attribution())
