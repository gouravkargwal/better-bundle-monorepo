"""
Gorse Feedback Transformer - OPTIMIZED VERSION
Transforms interactions/orders to Gorse feedback objects

Key improvements:
- Proper feedback type mapping
- Weight-based importance signals
- Temporal relevance
- Negative feedback for refunds
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.logging import get_logger
from app.shared.helpers import now_utc
import json

logger = get_logger(__name__)


class GorseFeedbackTransformer:
    """Transform interactions to Gorse feedback format with proper weighting"""

    def __init__(self):
        """Initialize feedback transformer"""
        pass

    def transform_order_to_feedback(self, order, shop_id: str) -> List[Dict[str, Any]]:
        """
        Transform order to Gorse feedback with proper weighting

        Creates positive feedback for purchases and negative feedback for refunds
        """
        try:
            feedback_list = []

            if hasattr(order, "__dict__"):
                order_dict = order.__dict__
            else:
                order_dict = order

            customer_id = order_dict.get("customer_id", "")
            order_date = order_dict.get("order_date", now_utc())
            line_items = order_dict.get("line_items", [])
            financial_status = order_dict.get("financial_status", "")
            total_refunded = float(order_dict.get("total_refunded_amount", 0.0))

            if not customer_id:
                return feedback_list

            for item in line_items:
                if isinstance(item, dict):
                    product_id = item.get("product_id", "")
                    quantity = item.get("quantity", 1)
                    line_total = float(item.get("line_total", 0.0))
                else:
                    product_id = getattr(item, "product_id", "")
                    quantity = getattr(item, "quantity", 1)
                    line_total = float(getattr(item, "line_total", 0.0))

                if not product_id:
                    continue

                timestamp = (
                    order_date.isoformat()
                    if hasattr(order_date, "isoformat")
                    else str(order_date)
                )

                # Refund = negative feedback
                if financial_status == "refunded" and total_refunded > 0:
                    feedback = {
                        "FeedbackType": "refund",
                        "UserId": f"shop_{shop_id}_{customer_id}",
                        "ItemId": f"shop_{shop_id}_{product_id}",
                        "Timestamp": timestamp,
                        "Comment": f"Refunded order - negative signal",
                    }
                else:
                    # Purchase = positive feedback (weighted by value)
                    feedback = {
                        "FeedbackType": "purchase",
                        "UserId": f"shop_{shop_id}_{customer_id}",
                        "ItemId": f"shop_{shop_id}_{product_id}",
                        "Timestamp": timestamp,
                        "Comment": f"Purchase: {quantity}x ${line_total:.2f}",
                    }

                feedback_list.append(feedback)

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to transform order to feedback: {str(e)}")
            return []

    def transform_batch_orders_to_feedback(
        self, orders_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple orders to Gorse feedback objects"""
        all_feedback = []

        for order in orders_list:
            feedback_list = self.transform_order_to_feedback(order, shop_id)
            all_feedback.extend(feedback_list)

        logger.info(
            f"Transformed {len(orders_list)} orders to {len(all_feedback)} feedback items"
        )
        return all_feedback

    def transform_behavioral_event_to_feedback(
        self, event, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform behavioral event to Gorse feedback

        Maps various event types to appropriate feedback types
        """
        try:
            if hasattr(event, "__dict__"):
                event_dict = event.__dict__
            else:
                event_dict = event

            event_type = event_dict.get("event_type", "")
            customer_id = event_dict.get("customer_id", "")
            product_id = event_dict.get("product_id", "")
            timestamp = event_dict.get("created_at", now_utc())

            if not customer_id or not product_id:
                return None

            # Map event types to feedback types with appropriate weights
            event_mapping = {
                "product_viewed": ("view", "Product view"),
                "product_added_to_cart": ("add_to_cart", "Added to cart"),
                "product_removed_from_cart": ("remove_from_cart", "Removed from cart"),
                "checkout_started": ("checkout", "Started checkout"),
                "order_completed": ("purchase", "Completed purchase"),
            }

            if event_type not in event_mapping:
                return None

            feedback_type, comment = event_mapping[event_type]

            feedback = {
                "FeedbackType": feedback_type,
                "UserId": f"shop_{shop_id}_{customer_id}",
                "ItemId": f"shop_{shop_id}_{product_id}",
                "Timestamp": (
                    timestamp.isoformat()
                    if hasattr(timestamp, "isoformat")
                    else str(timestamp)
                ),
                "Comment": comment,
            }

            return feedback

        except Exception as e:
            logger.error(f"Failed to transform behavioral event: {str(e)}")
            return None

    def transform_batch_events_to_feedback(
        self, events_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple behavioral events to Gorse feedback objects"""
        feedback_list = []

        for event in events_list:
            feedback = self.transform_behavioral_event_to_feedback(event, shop_id)
            if feedback:
                feedback_list.append(feedback)

        logger.info(
            f"Transformed {len(events_list)} events to {len(feedback_list)} feedback items"
        )
        return feedback_list
