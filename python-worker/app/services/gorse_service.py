"""
Gorse integration service for training models and serving recommendations
"""

from app.core.logger import get_logger
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import httpx
import json
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import get_database
from app.core.logger import get_logger

logger = get_logger(__name__)


class GorseService:
    """Service for integrating with Gorse recommendation engine"""

    def __init__(self):
        self.db = None
        self.base_url = settings.GORSE_BASE_URL
        self.api_key = settings.GORSE_API_KEY
        self.master_key = settings.GORSE_MASTER_KEY

    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()
        logger.info("Gorse service initialized")

    async def train_model_for_shop(
        self, shop_id: str, shop_domain: str
    ) -> Dict[str, Any]:
        """Train recommendation model for a specific shop by sending data to Gorse"""
        try:
            start_time = asyncio.get_event_loop().time()

            logger.info(
                "Starting model training", shop_id=shop_id, shop_domain=shop_domain
            )

            # Step 1: Check if shop has enough data for training
            data_check = await self._check_training_data_requirements(shop_id)
            if not data_check["can_train"]:
                return {
                    "success": False,
                    "error": f"Insufficient data for training: {data_check['reason']}",
                    "data_summary": data_check,
                }

                # Step 1.5: Check if training should be skipped using two-tier approach
            # 1. Primary: Check ML table for recent training and data changes
            #    - More accurate: directly checks when we last trained and if data changed since then
            #    - Faster: single database query instead of complex event stream analysis
            #    - More reliable: based on actual training history, not external events
            # 2. Fallback: Check event streams for analysis completion and data changes
            #    - Useful when no ML training history exists
            #    - Provides backup detection method
            #    - Handles edge cases where ML table might be incomplete
            logger.info(f"🔍 Checking if training should be skipped for shop {shop_id}")

            # First, check ML table for recent training (primary method)
            # This checks if we've recently trained and if data has changed since then
            ml_table_skip_check = await self._should_skip_ml_training(shop_id)
            logger.info(f"🔍 ML table skip check result: {ml_table_skip_check}")

            if ml_table_skip_check["should_skip"]:
                logger.info(
                    "Skipping ML training - no data changes since last training (ML table check)",
                    shop_id=shop_id,
                    reason=ml_table_skip_check["reason"],
                    method="ml_table_check",
                    last_training=ml_table_skip_check.get("last_training"),
                    hours_since_training=ml_table_skip_check.get(
                        "hours_since_training"
                    ),
                )

                # Record the skipped training attempt in ML table for tracking and analytics
                # This helps us understand training patterns and optimize the skip logic
                # It also provides a complete audit trail of all training decisions
                await self._record_skipped_training(shop_id, ml_table_skip_check)

                return {
                    "success": True,
                    "shop_id": shop_id,
                    "shop_domain": shop_domain,
                    "skipped": True,
                    "reason": ml_table_skip_check["reason"],
                    "method": "ml_table_check",
                    "last_training": ml_table_skip_check.get("last_training"),
                    "hours_since_training": ml_table_skip_check.get(
                        "hours_since_training"
                    ),
                    "message": "Training skipped - no new data since last training (ML table check)",
                }

            # If ML table check doesn't indicate skip, fall back to event stream check
            # This is useful when we don't have ML training history but want to check
            # if data has changed since the last analysis completion
            logger.info(f"🔍 ML table check passed, falling back to event stream check")
            event_stream_skip_check = await self._should_skip_ml_training_fallback(
                shop_id
            )
            logger.info(f"🔍 Event stream skip check result: {event_stream_skip_check}")

            # Use the event stream check result
            skip_check = event_stream_skip_check

            if skip_check["should_skip"]:
                logger.info(
                    "Skipping ML training - no data changes detected (event stream fallback check)",
                    shop_id=shop_id,
                    reason=skip_check["reason"],
                    method=skip_check.get("method", "unknown"),
                    last_training=skip_check.get("last_training"),
                    hours_since_training=skip_check.get("hours_since_training"),
                    hours_since_last_order=skip_check.get("hours_since_last_order"),
                    hours_since_last_product=skip_check.get("hours_since_last_product"),
                )

                # Record the skipped training attempt in ML table for tracking and analytics
                # This helps us understand training patterns and optimize the skip logic
                # It also provides a complete audit trail of all training decisions
                await self._record_skipped_training(shop_id, skip_check)

                return {
                    "success": True,
                    "shop_id": shop_id,
                    "shop_domain": shop_domain,
                    "skipped": True,
                    "reason": skip_check["reason"],
                    "method": skip_check.get("method", "unknown"),
                    "last_training": skip_check.get("last_training"),
                    "hours_since_training": skip_check.get("hours_since_training"),
                    "hours_since_last_order": skip_check.get("hours_since_last_order"),
                    "hours_since_last_product": skip_check.get(
                        "hours_since_last_product"
                    ),
                    "message": "Training skipped - no new data since last training (event stream fallback check)",
                }

            # Step 2: Extract and prepare training data
            training_data = await self._prepare_training_data(shop_id)

            # Step 3: Send data to Gorse (Gorse will handle training automatically)
            gorse_result = await self._send_data_to_gorse(shop_domain, training_data)

            # Step 4: Update training metadata
            await self._update_training_metadata(shop_id, gorse_result)

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(
                f"Performance: model_training | duration_ms={duration_ms:.2f} | shop_id={shop_id}"
            )

            logger.info(
                "Data sent to Gorse successfully",
                shop_id=shop_id,
                duration_ms=duration_ms,
                items_count=training_data["items_count"],
                users_count=training_data["users_count"],
                feedback_count=training_data["feedback_count"],
            )

            return {
                "success": True,
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "gorse_result": gorse_result,
                "data_summary": data_check,
                "duration_ms": duration_ms,
                "message": "Data sent to Gorse for automatic training",
            }

        except Exception as e:
            logger.error(
                f"Train model error | operation=train_model | shop_id={shop_id} | error={str(e)}"
            )
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def _check_training_data_requirements(self, shop_id: str) -> Dict[str, Any]:
        """Check if shop has enough data for training"""
        try:
            # Count orders
            orders_count = await self.db.orderdata.count(where={"shopId": shop_id})

            # Count products
            products_count = await self.db.productdata.count(where={"shopId": shop_id})

            # Count customers
            customers_count = await self.db.customerdata.count(
                where={"shopId": shop_id}
            )

            can_train = (
                orders_count >= settings.MIN_ORDERS_FOR_TRAINING
                and products_count >= settings.MIN_PRODUCTS_FOR_TRAINING
            )

            reason = ""
            if not can_train:
                if orders_count < settings.MIN_ORDERS_FOR_TRAINING:
                    reason = f"Need at least {settings.MIN_ORDERS_FOR_TRAINING} orders, got {orders_count}"
                elif products_count < settings.MIN_PRODUCTS_FOR_TRAINING:
                    reason = f"Need at least {settings.MIN_PRODUCTS_FOR_TRAINING} products, got {products_count}"

            return {
                "can_train": can_train,
                "reason": reason,
                "orders_count": orders_count,
                "products_count": products_count,
                "customers_count": customers_count,
                "min_orders_required": settings.MIN_ORDERS_FOR_TRAINING,
                "min_products_required": settings.MIN_PRODUCTS_FOR_TRAINING,
            }

        except Exception as e:
            logger.error(
                "Error checking training data requirements",
                shop_id=shop_id,
                error=str(e),
            )
            return {"can_train": False, "reason": f"Error checking data: {str(e)}"}

    async def _should_skip_ml_training(self, shop_id: str) -> Dict[str, Any]:
        """Check if ML training should be skipped due to no data changes

        This is the primary method that checks the MLTrainingLog table to see if we've
        recently trained the model and if there have been any data changes since then.
        """
        try:
            # Get last successful training timestamp (exclude failed jobs)
            # We only consider completed training logs as valid "last training" references
            # Failed jobs are just for tracking purposes and don't represent actual training
            last_training = await self.db.mltraininglog.find_first(
                where={"shopId": shop_id, "status": "completed"},
                order={"completedAt": "desc"},
            )

            if not last_training:
                return {
                    "should_skip": False,
                    "reason": "no_previous_training",
                    "last_training": None,
                }

            # Check if data has changed since last training
            last_order = await self.db.orderdata.find_first(
                where={"shopId": shop_id}, order={"orderDate": "desc"}
            )

            last_product = await self.db.productdata.find_first(
                where={"shopId": shop_id}, order={"updatedAt": "desc"}
            )

            # Skip if no new data since last training
            if (
                last_order
                and last_order.orderDate <= last_training.completedAt
                and last_product
                and last_product.updatedAt <= last_training.completedAt
            ):
                return {
                    "should_skip": True,
                    "reason": "no_data_changes_since_last_training",
                    "last_training": last_training.completedAt,
                    "last_order": last_order.orderDate,
                    "last_product": last_product.updatedAt,
                    "hours_since_training": (
                        (
                            datetime.now(timezone.utc) - last_training.completedAt
                        ).total_seconds()
                        / 3600
                    ),
                }

            return {
                "should_skip": False,
                "reason": "data_has_changed",
                "last_training": last_training.completedAt,
                "last_order": last_order.orderDate if last_order else None,
                "last_product": last_product.updatedAt if last_product else None,
            }

        except Exception as e:
            logger.error(f"Error checking if training should be skipped: {e}")
            return {
                "should_skip": False,
                "reason": f"error_checking_status: {str(e)}",
                "last_training": None,
            }

    async def _should_skip_ml_training_fallback(self, shop_id: str) -> Dict[str, Any]:
        """Check if training should be skipped based on event stream data changes (fallback method)

        This method is used as a fallback when the ML table check doesn't indicate a skip.
        It checks for data changes since the last analysis completion event.
        """
        try:
            logger.info(
                f"🧠 Checking for data changes using event streams (fallback method) for shop {shop_id}"
            )

            # Get the latest analysis completion event for this shop
            latest_analysis = await self._get_latest_analysis_event(shop_id)

            if not latest_analysis:
                logger.info(
                    f"🧠 No previous analysis found - allowing training to proceed"
                )
                return {
                    "should_skip": False,
                    "reason": "no_previous_analysis",
                    "method": "event_based_detection",
                    "order_count": await self.db.orderdata.count(
                        where={"shopId": shop_id}
                    ),
                    "product_count": await self.db.productdata.count(
                        where={"shopId": shop_id}
                    ),
                }

            # Get the analysis completion timestamp
            analysis_time = latest_analysis.get("completion_timestamp")
            if not analysis_time:
                logger.info(f"🧠 No timestamp in analysis event - allowing training")
                return {
                    "should_skip": False,
                    "reason": "no_analysis_timestamp",
                    "method": "event_based_detection",
                }

            # Parse the timestamp
            try:
                from datetime import datetime

                analysis_datetime = datetime.fromisoformat(
                    analysis_time.replace("Z", "+00:00")
                )
            except Exception as e:
                logger.warning(f"Could not parse analysis timestamp: {e}")
                return {
                    "should_skip": False,
                    "reason": "timestamp_parse_error",
                    "method": "event_based_detection",
                }

            # Check for new orders since last analysis
            new_orders_count = await self.db.orderdata.count(
                where={"shopId": shop_id, "orderDate": {"gt": analysis_datetime}}
            )

            # Check for updated products since last analysis
            updated_products_count = await self.db.productdata.count(
                where={"shopId": shop_id, "updatedAt": {"gt": analysis_datetime}}
            )

            # Check for new products since last analysis
            new_products_count = await self.db.productdata.count(
                where={"shopId": shop_id, "createdAt": {"gt": analysis_datetime}}
            )

            # Get current total counts
            current_order_count = await self.db.orderdata.count(
                where={"shopId": shop_id}
            )
            current_product_count = await self.db.productdata.count(
                where={"shopId": shop_id}
            )

            # Calculate total changes
            total_changes = (
                new_orders_count + updated_products_count + new_products_count
            )

            logger.info(f"🧠 Event-based data change analysis for shop {shop_id}:")
            logger.info(f"  - Last analysis: {analysis_datetime}")
            logger.info(f"  - New orders since analysis: {new_orders_count}")
            logger.info(
                f"  - Updated products since analysis: {updated_products_count}"
            )
            logger.info(f"  - New products since analysis: {new_products_count}")
            logger.info(f"  - Total changes: {total_changes}")

            # Skip training only if there are NO changes
            if total_changes == 0:
                logger.info(f"🧠 No data changes detected - skipping training")
                return {
                    "should_skip": True,
                    "reason": "no_data_changes_since_last_analysis",
                    "method": "event_based_detection",
                    "last_analysis": analysis_datetime,
                    "new_orders": new_orders_count,
                    "updated_products": updated_products_count,
                    "new_products": new_products_count,
                    "total_changes": total_changes,
                    "current_order_count": current_order_count,
                    "current_product_count": current_product_count,
                }
            else:
                logger.info(f"🧠 Data changes detected - allowing training to proceed")
                return {
                    "should_skip": False,
                    "reason": f"data_changes_detected_{total_changes}_changes",
                    "method": "event_based_detection",
                    "last_analysis": analysis_datetime,
                    "new_orders": new_orders_count,
                    "updated_products": updated_products_count,
                    "new_products": new_products_count,
                    "total_changes": total_changes,
                    "current_order_count": current_order_count,
                    "current_product_count": current_product_count,
                }

        except Exception as e:
            logger.error(f"Error in event-based data change detection: {e}")
            return {
                "should_skip": False,
                "reason": f"detection_error: {str(e)}",
                "method": "event_based_detection_failed",
            }

    async def _get_latest_analysis_event(
        self, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the latest analysis completion event for a shop from the event stream"""
        try:
            from app.core.redis_client import streams_manager

            # Get the latest event from the analysis results stream
            events = await streams_manager.consume_events(
                stream_name="betterbundle:analysis-results",
                consumer_group="gorse-service",
                consumer_name=f"gorse-service-{shop_id}",
                count=10,  # Get last 10 events to find shop-specific ones
                block=1000,  # 1 second timeout
            )

            if not events:
                logger.info(f"No analysis events found in stream for shop {shop_id}")
                return None

            # Find the most recent event for this specific shop
            shop_events = [event for event in events if event.get("shop_id") == shop_id]

            if not shop_events:
                logger.info(f"No analysis events found for shop {shop_id}")
                return None

            # Return the most recent one (they should be ordered by timestamp)
            latest_event = shop_events[0]
            logger.info(
                f"Found latest analysis event for shop {shop_id}: {latest_event.get('event_type', 'unknown')}"
            )

            return latest_event

        except Exception as e:
            logger.error(f"Error getting latest analysis event: {e}")
            return None

    async def _prepare_training_data(self, shop_id: str) -> Dict[str, Any]:
        """Prepare training data for Gorse"""
        try:
            # Get orders with line items
            orders = await self.db.orderdata.find_many(where={"shopId": shop_id})

            # Get products
            products = await self.db.productdata.find_many(
                where={"shopId": shop_id, "isActive": True}
            )

            # Create product lookup
            product_lookup = {p.productId: p for p in products}

            # Prepare items for Gorse
            items = []
            for product in products:
                items.append(
                    {
                        "item_id": product.productId,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "categories": [product.category] if product.category else [],
                        "tags": [],
                        "labels": [],
                        "comment": product.title,
                    }
                )

            # Prepare users for Gorse
            users = []
            user_orders = {}

            for order in orders:
                if order.customerId:
                    if order.customerId not in user_orders:
                        user_orders[order.customerId] = []
                        users.append(
                            {
                                "user_id": order.customerId,
                                "labels": [],
                                # Removed subscribe field to avoid Gorse SQL storage bug
                                # "subscribe": [],  # This was causing JSON unmarshal errors
                                "comment": f"Customer from {shop_id}",
                            }
                        )

                    # Add order to user's history
                    user_orders[order.customerId].append(order)

            # Prepare feedback for Gorse
            feedback = []
            for order in orders:
                if order.customerId and order.lineItems:
                    line_items = (
                        order.lineItems
                        if isinstance(order.lineItems, list)
                        else json.loads(order.lineItems)
                    )

                    for item in line_items:
                        if item.get("product_id") in product_lookup:
                            feedback.append(
                                {
                                    "feedback_type": "star",
                                    "user_id": order.customerId,
                                    "item_id": item["product_id"],
                                    "timestamp": order.orderDate.isoformat(),
                                    "comment": f"Purchase from order {order.id}",
                                }
                            )

            return {
                "items": items,
                "users": users,
                "feedback": feedback,
                "items_count": len(items),
                "users_count": len(users),
                "feedback_count": len(feedback),
            }

        except Exception as e:
            logger.error("Error preparing training data", shop_id=shop_id, error=str(e))
            raise

    async def _send_data_to_gorse(
        self, shop_domain: str, training_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send training data to Gorse using batch operations for optimal performance"""
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Insert items in batches (Gorse supports batch operations)
                items_success = 0
                items_total = len(training_data["items"])

                # Process items in batches of 100 for optimal performance
                batch_size = 100
                for i in range(0, items_total, batch_size):
                    batch = training_data["items"][i : i + batch_size]
                    try:
                        # Use batch endpoint if available, otherwise fallback to individual
                        batch_response = await self._batch_insert_items(client, batch)
                        if batch_response:
                            items_success += len(batch)
                        else:
                            # Fallback to individual inserts for this batch
                            for item in batch:
                                try:
                                    item_response = await client.post(
                                        f"{self.base_url}/api/item",
                                        headers={"X-API-Key": self.master_key},
                                        json=item,
                                        timeout=30.0,
                                    )
                                    if item_response.status_code == 200:
                                        items_success += 1
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to insert item {item.get('ItemId', 'unknown')}: {e}"
                                    )
                    except Exception as batch_error:
                        logger.warning(
                            f"Batch insert failed for items {i}-{i+batch_size}: {batch_error}"
                        )
                        # Fallback to individual inserts for this batch
                        for item in batch:
                            try:
                                item_response = await client.post(
                                    f"{self.base_url}/api/item",
                                    headers={"X-API-Key": self.master_key},
                                    json=item,
                                    timeout=30.0,
                                )
                                if item_response.status_code == 200:
                                    items_success += 1
                            except Exception as e:
                                logger.warning(
                                    f"Failed to insert item {item.get('ItemId', 'unknown')}: {e}"
                                )

                logger.info(
                    f"Inserted {items_success}/{items_total} items successfully"
                )

                # Step 2: Insert users in batches
                users_success = 0
                users_total = len(training_data["users"])

                # Process users in batches of 100
                for i in range(0, users_total, batch_size):
                    batch = training_data["users"][i : i + batch_size]
                    try:
                        # Use batch endpoint if available, otherwise fallback to individual
                        batch_response = await self._batch_insert_users(client, batch)
                        if batch_response:
                            users_success += len(batch)
                        else:
                            # Fallback to individual inserts for this batch
                            for user in batch:
                                try:
                                    user_response = await client.post(
                                        f"{self.base_url}/api/user",
                                        headers={"X-API-Key": self.master_key},
                                        json=user,
                                        timeout=30.0,
                                    )
                                    if user_response.status_code == 200:
                                        users_success += 1
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to insert user {user.get('user_id', 'unknown')}: {e}"
                                    )
                    except Exception as batch_error:
                        logger.warning(
                            f"Batch insert failed for users {i}-{i+batch_size}: {batch_error}"
                        )
                        # Fallback to individual inserts for this batch
                        for user in batch:
                            try:
                                user_response = await client.post(
                                    f"{self.base_url}/api/user",
                                    headers={"X-API-Key": self.master_key},
                                    json=user,
                                    timeout=30.0,
                                )
                                if user_response.status_code == 200:
                                    users_success += 1
                            except Exception as e:
                                logger.warning(
                                    f"Failed to insert user {user.get('user_id', 'unknown')}: {e}"
                                )

                logger.info(
                    f"Inserted {users_success}/{users_total} users successfully"
                )

                # Step 3: Insert feedback in batches (if any)
                feedback_success = 0
                feedback_total = len(training_data["feedback"])

                if feedback_total > 0:
                    # Process feedback in batches of 100
                    for i in range(0, feedback_total, batch_size):
                        batch = training_data["feedback"][i : i + batch_size]
                        try:
                            # Use batch endpoint if available, otherwise fallback to individual
                            batch_response = await self._batch_insert_feedback(
                                client, batch
                            )
                            if batch_response:
                                feedback_success += len(batch)
                            else:
                                # Fallback to individual inserts for this batch
                                for feedback_item in batch:
                                    try:
                                        feedback_response = await client.post(
                                            f"{self.base_url}/api/feedback",
                                            headers={"X-API-Key": self.master_key},
                                            json=feedback_item,
                                            timeout=30.0,
                                        )
                                        if feedback_response.status_code == 200:
                                            feedback_success += 1
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to insert feedback: {e}"
                                        )
                        except Exception as batch_error:
                            logger.warning(
                                f"Batch insert failed for feedback {i}-{i+batch_size}: {batch_error}"
                            )
                            # Fallback to individual inserts for this batch
                            for feedback_item in batch:
                                try:
                                    feedback_response = await client.post(
                                        f"{self.base_url}/api/feedback",
                                        headers={"X-API-Key": self.master_key},
                                        json=feedback_item,
                                        timeout=30.0,
                                    )
                                    if feedback_response.status_code == 200:
                                        feedback_success += 1
                                except Exception as e:
                                    logger.warning(f"Failed to insert feedback: {e}")

                    logger.info(
                        f"Inserted {feedback_success}/{feedback_total} feedback records successfully"
                    )

                # Note: Gorse will automatically start training when new data is inserted
                # We don't need to explicitly trigger training

                return {
                    "items_inserted": items_success > 0,
                    "users_inserted": users_success > 0,
                    "feedback_inserted": feedback_success > 0,
                    "items_count": items_success,
                    "users_count": users_success,
                    "feedback_count": feedback_success,
                    "training_automatic": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": f"Data sent to Gorse - {items_success} items, {users_success} users, {feedback_success} feedback records inserted",
                }

        except Exception as e:
            logger.error("Error sending data to Gorse", error=str(e))
            raise

    async def _update_training_metadata(
        self, shop_id: str, gorse_result: Dict[str, Any]
    ):
        """Update training metadata in database"""
        try:
            # Check if there's an existing training log for this shop
            existing_log = await self.db.mltraininglog.find_first(
                where={"shopId": shop_id, "status": "started"},
                order={"createdAt": "desc"},
            )

            if existing_log:
                # Update existing log
                await self.db.mltraininglog.update(
                    where={"id": existing_log.id},
                    data={
                        "status": (
                            "completed"
                            if gorse_result.get("items_inserted")
                            else "failed"
                        ),
                        "completedAt": (
                            datetime.now(timezone.utc)
                            if gorse_result.get("items_inserted")
                            else None
                        ),
                        "durationMs": (
                            int(
                                (
                                    datetime.now(timezone.utc) - existing_log.startedAt
                                ).total_seconds()
                                * 1000
                            )
                            if existing_log.startedAt
                            else None
                        ),
                        "productsCount": gorse_result.get("items_inserted", 0),
                        "usersCount": gorse_result.get("users_inserted", 0),
                        "error": (
                            None if gorse_result.get("items_inserted") else "failed"
                        ),
                    },
                )
                logger.info(
                    "Training log updated",
                    shop_id=shop_id,
                    log_id=existing_log.id,
                    status=(
                        "completed" if gorse_result.get("items_inserted") else "failed"
                    ),
                )
            else:
                # Create new completed log
                await self.db.mltraininglog.create(
                    data={
                        "shopId": shop_id,
                        "status": (
                            "completed"
                            if gorse_result.get("items_inserted")
                            else "failed"
                        ),
                        "startedAt": datetime.now(timezone.utc),
                        "completedAt": (
                            datetime.now(timezone.utc)
                            if gorse_result.get("items_inserted")
                            else None
                        ),
                        "durationMs": 0,  # No duration for immediate completion
                        "productsCount": gorse_result.get("items_inserted", 0),
                        "usersCount": gorse_result.get("users_inserted", 0),
                        "error": (
                            None
                            if gorse_result.get("items_inserted")
                            else "Data insertion failed"
                        ),
                    }
                )
                logger.info(
                    "Training log created",
                    shop_id=shop_id,
                    status=(
                        "completed" if gorse_result.get("items_inserted") else "failed"
                    ),
                )

        except Exception as e:
            logger.error(
                "Error updating training metadata", shop_id=shop_id, error=str(e)
            )

    async def _record_skipped_training(self, shop_id: str, skip_check: Dict[str, Any]):
        """Record a skipped training attempt in the ML table for tracking purposes

        This method creates a record in the MLTrainingLog table with status 'skipped' to track
        when and why training was skipped. This helps with:
        - Analytics on training patterns
        - Debugging skip logic
        - Understanding shop behavior
        - Optimizing the skip thresholds
        """
        try:
            # Create a record for the skipped training
            await self.db.mltraininglog.create(
                data={
                    "shopId": shop_id,
                    "status": "skipped",
                    "startedAt": datetime.now(timezone.utc),
                    "completedAt": datetime.now(
                        timezone.utc
                    ),  # Same as started since it's skipped
                    "durationMs": 0,  # No duration since training was skipped
                    "productsCount": 0,  # No products processed
                    "usersCount": 0,  # No users processed
                    "error": f"Skipped: {skip_check.get('reason', 'unknown')}",
                }
            )

            logger.info(
                "Skipped training recorded in ML table",
                shop_id=shop_id,
                reason=skip_check.get("reason"),
                method=skip_check.get("method", "unknown"),
            )

        except Exception as e:
            # Log error but don't fail the main training flow
            # Recording skipped training is not critical for the main functionality
            logger.error(
                "Error recording skipped training", shop_id=shop_id, error=str(e)
            )

    async def get_recommendations(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        item_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recommendations from Gorse"""
        try:
            # Build recommendation URL
            if user_id:
                # User-based recommendations
                url = f"{self.base_url}/api/recommend/user/{user_id}"
            elif item_id:
                # Item-based recommendations
                url = f"{self.base_url}/api/recommend/item/{item_id}"
            else:
                # Popular items
                url = f"{self.base_url}/api/popular"

            # Add category filter if specified
            if category:
                url += f"?category={category}"

            # Add limit
            url += f"{'&' if '?' in url else '?'}n={settings.MAX_RECOMMENDATIONS}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, headers={"X-API-Key": self.api_key}, timeout=10.0
                )

                if response.status_code == 200:
                    recommendations = response.json()

                    # Filter by confidence threshold
                    filtered_recommendations = [
                        rec
                        for rec in recommendations
                        if rec.get("Score", 0) >= settings.MIN_CONFIDENCE_THRESHOLD
                    ]

                    return {
                        "success": True,
                        "shop_id": shop_id,
                        "user_id": user_id,
                        "item_id": item_id,
                        "category": category,
                        "recommendations": filtered_recommendations,
                        "total_count": len(filtered_recommendations),
                        "confidence_threshold": settings.MIN_CONFIDENCE_THRESHOLD,
                    }
                else:
                    logger.error(
                        "Failed to get recommendations",
                        status_code=response.status_code,
                    )
                    return {
                        "success": False,
                        "error": f"Gorse API error: {response.status_code}",
                        "shop_id": shop_id,
                    }

        except Exception as e:
            logger.error(
                f"Get recommendations error | operation=get_recommendations | shop_id={shop_id} | error={str(e)}"
            )
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def submit_feedback(
        self,
        shop_id: str,
        user_id: str,
        item_id: str,
        feedback_type: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit feedback to Gorse"""
        try:
            feedback_data = {
                "feedback_type": feedback_type,
                "user_id": user_id,
                "item_id": item_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if comment:
                feedback_data["comment"] = comment

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/feedback",
                    headers={"X-API-Key": self.master_key},
                    json=feedback_data,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info(
                        "Feedback submitted successfully",
                        shop_id=shop_id,
                        user_id=user_id,
                        item_id=item_id,
                        feedback_type=feedback_type,
                    )

                    return {
                        "success": True,
                        "feedback_id": response.json().get("RowAffected"),
                        "shop_id": shop_id,
                    }
                else:
                    logger.error(
                        "Failed to submit feedback", status_code=response.status_code
                    )
                    return {
                        "success": False,
                        "error": f"Gorse API error: {response.status_code}",
                        "shop_id": shop_id,
                    }

        except Exception as e:
            logger.error(
                f"Submit feedback error | operation=submit_feedback | shop_id={shop_id} | error={str(e)}"
            )
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def get_model_status(self, shop_id: str) -> Dict[str, Any]:
        """Get model training status for a shop"""
        try:
            # Query the MLTrainingLog table for this shop
            training_logs = await self.db.mltraininglog.find_many(
                where={"shopId": shop_id},
                order={"createdAt": "desc"},
                take=5,  # Get last 5 training logs
            )

            if not training_logs:
                return {
                    "success": True,
                    "shop_id": shop_id,
                    "model_status": "never_trained",
                    "last_training": None,
                    "training_count": 0,
                    "recommendations_available": False,
                    "message": "No training jobs found for this shop",
                }

            # Get the most recent training log
            latest_log = training_logs[0]

            # Check if there are any completed logs
            completed_logs = [log for log in training_logs if log.status == "completed"]
            failed_logs = [log for log in training_logs if log.status == "failed"]

            # Determine overall status
            if latest_log.status == "started":
                model_status = "training_in_progress"
            elif latest_log.status == "completed":
                model_status = "trained"
            elif latest_log.status == "failed":
                model_status = "training_failed"
            else:
                model_status = "unknown"

            return {
                "success": True,
                "shop_id": shop_id,
                "model_status": model_status,
                "latest_log": {
                    "id": latest_log.id,
                    "status": latest_log.status,
                    "started_at": (
                        latest_log.startedAt.isoformat()
                        if latest_log.startedAt
                        else None
                    ),
                    "completed_at": (
                        latest_log.completedAt.isoformat()
                        if latest_log.completedAt
                        else None
                    ),
                    "duration_ms": latest_log.durationMs,
                    "products_count": latest_log.productsCount,
                    "users_count": latest_log.usersCount,
                    "error": latest_log.error,
                },
                "training_count": len(training_logs),
                "completed_count": len(completed_logs),
                "failed_count": len(failed_logs),
                "recommendations_available": model_status == "trained",
                "last_training": (
                    latest_log.completedAt.isoformat()
                    if latest_log.completedAt
                    else None
                ),
            }

        except Exception as e:
            logger.error(
                f"Get model status error | operation=get_model_status | shop_id={shop_id} | error={str(e)}"
            )
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def check_gorse_health(self) -> Dict[str, Any]:
        """Check if Gorse service is healthy"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/health",
                    headers={"X-API-Key": self.api_key},
                    timeout=5.0,
                )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "status": "healthy",
                        "gorse_url": self.base_url,
                    }
                else:
                    return {
                        "success": False,
                        "status": "unhealthy",
                        "gorse_url": self.base_url,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "success": False,
                "status": "unhealthy",
                "gorse_url": self.base_url,
                "error": str(e),
            }

    async def _batch_insert_items(
        self, client: httpx.AsyncClient, items: List[Dict[str, Any]]
    ) -> bool:
        """Insert multiple items in a single API call to Gorse"""
        try:
            # Gorse supports batch item insertion via POST /api/items (plural)
            response = await client.post(
                f"{self.base_url}/api/items",
                headers={"X-API-Key": self.master_key},
                json=items,  # Send array of items
                timeout=60.0,  # Longer timeout for batch operations
            )
            if response.status_code == 200:
                logger.info(f"Batch inserted {len(items)} items successfully")
                return True
            else:
                logger.warning(
                    f"Batch insert failed with status {response.status_code}"
                )
                return False
        except Exception as e:
            logger.warning(f"Batch insert items failed: {e}")
            return False

    async def _batch_insert_users(
        self, client: httpx.AsyncClient, users: List[Dict[str, Any]]
    ) -> bool:
        """Insert multiple users in a single API call to Gorse"""
        try:
            # Gorse supports batch user insertion via POST /api/users (plural)
            response = await client.post(
                f"{self.base_url}/api/users",
                headers={"X-API-Key": self.master_key},
                json=users,  # Send array of users
                timeout=60.0,  # Longer timeout for batch operations
            )
            if response.status_code == 200:
                logger.info(f"Batch inserted {len(users)} users successfully")
                return True
            else:
                logger.warning(
                    f"Batch insert failed with status {response.status_code}"
                )
                return False
        except Exception as e:
            logger.warning(f"Batch insert users failed: {e}")
            return False

    async def _batch_insert_feedback(
        self, client: httpx.AsyncClient, feedback: List[Dict[str, Any]]
    ) -> bool:
        """Insert multiple feedback records in a single API call to Gorse"""
        try:
            # Gorse supports batch feedback insertion via POST /api/feedback (plural)
            response = await client.post(
                f"{self.base_url}/api/feedback",
                headers={"X-API-Key": self.master_key},
                json=feedback,  # Send array of feedback records
                timeout=60.0,  # Longer timeout for batch operations
            )
            if response.status_code == 200:
                logger.info(
                    f"Batch inserted {len(feedback)} feedback records successfully"
                )
                return True
            else:
                logger.warning(
                    f"Batch insert failed with status {response.status_code}"
                )
                return False
        except Exception as e:
            logger.warning(f"Batch insert feedback failed: {e}")
            return False


# Global instance
gorse_service = GorseService()
