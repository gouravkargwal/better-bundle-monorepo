"""
Feedback synchronization logic for Gorse pipeline
Handles feedback data processing, streaming, and syncing
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.shared.decorators import retry_with_exponential_backoff
from prisma.errors import PrismaError

logger = get_logger(__name__)


class GorseFeedbackSync:
    """Feedback synchronization operations"""

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def _get_prefixed_user_id(self, user_id: str, shop_id: str) -> str:
        """
        Generate shop-prefixed user ID for multi-tenancy
        Format: shop_{shop_id}_{user_id}
        """
        if not shop_id:
            return user_id

        # Check if user_id is already prefixed to avoid double prefixing
        if user_id.startswith(f"shop_{shop_id}_"):
            return user_id

        # Extract numeric ID from Shopify GID if present
        numeric_id = self._extract_numeric_id_from_shopify_gid(user_id)
        if numeric_id:
            return f"shop_{shop_id}_{numeric_id}"

        return f"shop_{shop_id}_{user_id}"

    def _get_prefixed_item_id(self, item_id: str, shop_id: str) -> str:
        """
        Generate shop-prefixed item ID for multi-tenancy
        Format: shop_{shop_id}_{item_id}
        """
        if not shop_id:
            return item_id

        # Check if item_id is already prefixed to avoid double prefixing
        if item_id.startswith(f"shop_{shop_id}_"):
            return item_id

        # Extract numeric ID from Shopify GID if present
        numeric_id = self._extract_numeric_id_from_shopify_gid(item_id)
        if numeric_id:
            return f"shop_{shop_id}_{numeric_id}"

        return f"shop_{shop_id}_{item_id}"

    def _extract_numeric_id_from_shopify_gid(self, gid: str) -> Optional[str]:
        """
        Extract numeric ID from Shopify GID
        Examples:
        - gid://shopify/Product/75170 -> 75170
        - gid://shopify/ProductVariant/75183 -> 75183
        - 75170 -> 75170 (already numeric)
        """
        if not gid:
            return None

        # If it's already numeric, return as is
        if gid.isdigit():
            return gid

        # Extract from Shopify GID format
        if "gid://shopify/" in gid:
            parts = gid.split("/")
            if len(parts) >= 4:
                return parts[-1]  # Last part is the numeric ID

        return None

    async def sync_feedback(self, shop_id: str, since_hours: int = 24):
        """
        Sync feedback data from multiple sources to Gorse using streaming processing
        Processes behavioral events, orders, interactions, and sessions without loading all data into memory
        with transactional integrity
        """

        async def _sync_feedback_operation():
            if since_hours == 0:
                logger.info(
                    f"Starting streaming feedback sync for shop {shop_id} (ALL historical data) with batch size {self.pipeline.feedback_batch_size}"
                )
                since_time = None  # None means no time filter - get all data
            else:
                logger.info(
                    f"Starting streaming feedback sync for shop {shop_id} (last {since_hours} hours) with batch size {self.pipeline.feedback_batch_size}"
                )
                since_time = now_utc() - timedelta(hours=since_hours)

            total_synced = 0

            # Create streaming generators for each feedback source
            feedback_streams = [
                self.pipeline._stream_behavioral_events(shop_id, since_time),
                self.pipeline._stream_orders(shop_id, since_time),
                self.pipeline._stream_interaction_features(shop_id, since_time),
                self.pipeline._stream_session_feedback(shop_id, since_time),
            ]

            # Process feedback streams concurrently using asyncio.gather
            # Each stream yields batches of feedback that we process immediately
            stream_tasks = [
                self._process_feedback_stream(stream) for stream in feedback_streams
            ]

            # Wait for all streams to complete and sum up the results
            stream_results = await asyncio.gather(*stream_tasks)
            total_synced = sum(stream_results)

            logger.info(
                f"Streaming sync completed: {total_synced} feedback records synced for shop {shop_id}"
            )
            return total_synced

        # Feedback sync doesn't use transactions due to streaming processing
        # Each batch insert is atomic, but the overall sync is not wrapped in a transaction
        # to avoid timeout issues with long-running streaming operations
        await _sync_feedback_operation()

    async def _process_feedback_stream(self, feedback_stream) -> int:
        """
        Process a single feedback stream, yielding batches and inserting them immediately
        Returns the total number of records processed from this stream
        """
        total_synced = 0
        batch_buffer = []

        try:
            async for feedback_batch in feedback_stream:
                # Add to buffer
                batch_buffer.extend(feedback_batch)

                # Process buffer when it reaches batch size
                if len(batch_buffer) >= self.pipeline.feedback_batch_size:
                    # Resolve user identities before further processing
                    resolved_batch = await self._resolve_user_identities(batch_buffer)

                    # Deduplicate the batch
                    unique_batch = self._deduplicate_feedback(resolved_batch)

                    # Insert the batch
                    batch_count = await self._bulk_insert_gorse_feedback(unique_batch)
                    total_synced += batch_count

                    logger.debug(
                        f"Processed streaming batch: {len(unique_batch)} records, total: {total_synced}"
                    )

                    # Clear buffer
                    batch_buffer = []

            # Process any remaining records in buffer
            if batch_buffer:
                resolved_batch = await self._resolve_user_identities(batch_buffer)
                unique_batch = self._deduplicate_feedback(resolved_batch)
                batch_count = await self._bulk_insert_gorse_feedback(unique_batch)
                total_synced += batch_count

                logger.debug(
                    f"Processed final streaming batch: {len(unique_batch)} records, total: {total_synced}"
                )

        except Exception as e:
            logger.error(f"Error processing feedback stream: {str(e)}")
            raise

        return total_synced

    async def _resolve_user_identities(
        self, feedback_batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for and stitch user identities from anonymous to known"""
        # Find all anonymous session IDs in the batch
        session_ids = {
            f["user_id"].replace("session_", "")
            for f in feedback_batch
            if f.get("user_id", "").startswith("session_")
        }

        if not session_ids:
            return feedback_batch

        try:
            db = await self.pipeline._get_database()
            links = await db.useridentitylink.find_many(
                where={"clientId": {"in": list(session_ids)}}
            )

            if not links:
                return feedback_batch

            # Create a mapping from clientId to customerId
            id_map = {link.clientId: link.customerId for link in links}
            logger.debug(f"Found {len(id_map)} identity links for this batch.")

            # Create a new batch with resolved IDs
            resolved_batch = []
            for feedback in feedback_batch:
                user_id = feedback.get("user_id")
                if user_id and user_id.startswith("session_"):
                    client_id = user_id.replace("session_", "")
                    if client_id in id_map:
                        # Swap anonymous ID for the permanent customer ID
                        feedback["user_id"] = id_map[client_id]
                        logger.debug(
                            f"Stitched identity: {user_id} -> {id_map[client_id]}"
                        )
                resolved_batch.append(feedback)

            return resolved_batch

        except Exception as e:
            logger.error(f"Failed during user identity resolution: {str(e)}")
            # Return original batch on error to avoid data loss
            return feedback_batch

    @retry_with_exponential_backoff(max_retries=2, base_delay=1.0)
    async def _bulk_insert_gorse_feedback(
        self, feedback_batch: List[Dict[str, Any]]
    ) -> int:
        """Bulk insert feedback records to GorseFeedback table using true bulk operations"""
        if not feedback_batch:
            return 0

        try:
            db = await self.pipeline._get_database()

            # Convert feedback to Gorse schema format with prefixed IDs for multi-tenancy
            gorse_feedback_data = []
            for feedback in feedback_batch:
                # Use prefixed IDs for multi-tenancy
                prefixed_user_id = self._get_prefixed_user_id(
                    feedback["userId"], feedback["shop_id"]
                )
                prefixed_item_id = self._get_prefixed_item_id(
                    feedback["itemId"], feedback["shop_id"]
                )

                gorse_feedback_record = {
                    "feedback_type": feedback["feedbackType"],
                    "user_id": prefixed_user_id,
                    "item_id": prefixed_item_id,
                    "timestamp": feedback["timestamp"],
                    "shop_id": feedback["shop_id"],
                    "comment": feedback.get("comment"),
                }
                gorse_feedback_data.append(gorse_feedback_record)

            # Use Prisma's create_many for true bulk insert with skip_duplicates
            # This is much more efficient than individual inserts
            try:
                result = await db.gorsefeedback.create_many(
                    data=gorse_feedback_data,
                    skip_duplicates=True,  # Skip records that violate unique constraints
                )
                # create_many returns the count directly, not as result.count
                total_inserted = result
                logger.debug(
                    f"Bulk inserted {total_inserted} feedback records using create_many"
                )
                return total_inserted

            except (PrismaError, asyncio.TimeoutError, ConnectionError) as bulk_error:
                # Fallback to chunked processing if bulk insert fails
                logger.warning(
                    f"Bulk insert failed, falling back to chunked processing: {str(bulk_error)}"
                )
                return await self._fallback_chunked_feedback_insert(gorse_feedback_data)
            except Exception as bulk_error:
                # For non-transient errors, don't retry
                logger.error(f"Non-retryable error in bulk insert: {str(bulk_error)}")
                raise

        except (PrismaError, asyncio.TimeoutError, ConnectionError) as e:
            logger.error(f"Database error in bulk insert Gorse feedback: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in bulk insert Gorse feedback: {str(e)}")
            raise

    async def _fallback_chunked_feedback_insert(
        self, gorse_feedback_data: List[Dict[str, Any]]
    ) -> int:
        """Fallback method for chunked feedback insertion when bulk insert fails"""
        chunk_size = 200  # Process 200 feedback records at a time
        total_inserted = 0

        for i in range(0, len(gorse_feedback_data), chunk_size):
            chunk = gorse_feedback_data[i : i + chunk_size]

            # Use asyncio.gather for concurrent inserts within each chunk
            insert_tasks = []
            for feedback_data in chunk:
                insert_tasks.append(self._safe_insert_feedback(feedback_data))

            # Execute all inserts in this chunk concurrently
            results = await asyncio.gather(*insert_tasks, return_exceptions=True)

            # Count successful insertions
            successful_inserts = sum(1 for result in results if result is True)
            total_inserted += successful_inserts

            logger.debug(
                f"Processed feedback chunk: {successful_inserts}/{len(chunk)} inserted"
            )

        return total_inserted

    async def _safe_insert_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """Safely insert a single feedback record, handling duplicates"""
        try:
            db = await self.pipeline._get_database()

            await db.gorsefeedback.create(data=feedback_data)
            return True

        except Exception as e:
            # If it's a unique constraint violation, it's likely a duplicate, so we can skip it
            error_str = str(e).lower()
            if "unique constraint" in error_str or "duplicate" in error_str:
                logger.debug(
                    f"Skipped duplicate Gorse feedback: {feedback_data['feedbackType']} "
                    f"for user {feedback_data['userId']} on item {feedback_data['itemId']}"
                )
                return False
            else:
                # Re-raise if it's not a duplicate error
                logger.error(f"Failed to insert feedback: {str(e)}")
                logger.debug(f"Problematic feedback data: {feedback_data}")
                return False

    def _convert_event_to_feedback(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert behavioral event to feedback"""
        feedback_list = []

        event_type = event.get("eventType", "")
        event_data = event.get("eventData", {})

        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        # Determine user ID
        user_id = event.get("customerId")
        if not user_id:
            client_id = event.get(
                "clientId"
            )  # clientId is in the main event, not event_data
            if client_id:
                user_id = f"session_{client_id}"
            else:
                return []

        # Map event types to feedback with optimized weights
        feedback_mapping = {
            "product_viewed": ("view", 1.0),
            "product_added_to_cart": ("cart_add", 5.0),  # Increased
            "collection_viewed": ("collection_view", 0.5),
            "search_submitted": ("search", 0.3),
            "checkout_started": ("checkout_start", 7.0),  # Increased
            "checkout_completed": ("purchase", 10.0),  # Maximum weight
        }

        if event_type in feedback_mapping:
            feedback_type, base_weight = feedback_mapping[event_type]

            product_id = self.pipeline.transformers._extract_product_id_from_event(
                event_data
            )

            if product_id:
                # Apply time decay to weight
                timestamp = event.get("timestamp")
                decayed_weight = (
                    base_weight
                    * self.pipeline.transformers._apply_time_decay(timestamp)
                )

                # Apply the same user ID and item ID prefixing as user/item sync
                prefixed_user_id = self._get_prefixed_user_id(
                    user_id, event.get("shopId")
                )
                prefixed_item_id = self._get_prefixed_item_id(
                    product_id, event.get("shopId")
                )

                feedback_list.append(
                    {
                        "feedback_type": feedback_type,
                        "user_id": prefixed_user_id,
                        "item_id": prefixed_item_id,
                        "timestamp": timestamp,
                        "shop_id": event.get("shopId"),
                        "comment": json.dumps({"weight": decayed_weight}),
                    }
                )

        return feedback_list

    def _convert_order_to_feedback(self, order: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert order data to feedback"""
        feedback_list = []

        try:
            # Extract user ID (prefer customerId, fallback to email)
            user_id = order.get("customerId")
            if not user_id:
                user_id = order.get("customerEmail")

            if not user_id:
                logger.warning(f"No user ID found for order {order.get('orderId')}")
                return []

            # Extract line items (JSON array of products)
            line_items = order.get("lineItems", [])
            if isinstance(line_items, str):
                try:
                    line_items = json.loads(line_items)
                except:
                    line_items = []

            if not line_items:
                logger.debug(f"No line items found for order {order.get('orderId')}")
                return []

            # Get order metadata
            order_date = order.get("orderDate")
            shop_id = order.get("shopId")
            order_id = order.get("orderId")
            total_amount = float(order.get("totalAmount", 0))

            # Process each line item to create purchase feedback
            for item in line_items:
                try:
                    # Extract product ID from line item
                    product_id = None

                    # Try different possible structures for line items
                    if isinstance(item, dict):
                        # Check for variant -> product -> id structure
                        if "variant" in item and item["variant"]:
                            variant = item["variant"]
                            if isinstance(variant, dict) and "product" in variant:
                                product = variant["product"]
                                if isinstance(product, dict):
                                    product_id = product.get("id")

                        # Fallback: check for direct product_id or productId
                        if not product_id:
                            product_id = item.get("product_id") or item.get("productId")

                        # Another fallback: check for id field
                        if not product_id:
                            product_id = item.get("id")

                    if not product_id:
                        logger.debug(f"No product ID found in line item: {item}")
                        continue

                    # Extract quantity and price for weight calculation
                    quantity = int(item.get("quantity", 1))
                    line_total = 0

                    # Try to get line item value
                    if "variant" in item and item["variant"]:
                        variant = item["variant"]
                        if isinstance(variant, dict):
                            price = float(variant.get("price", 0))
                            line_total = price * quantity

                    # Calculate weight based on purchase value and quantity
                    base_weight = 10.0  # Strong weight for purchases

                    # Bonus for high-value orders
                    if total_amount > 100:
                        base_weight *= 1.2

                    # Apply time decay
                    decayed_weight = (
                        base_weight
                        * self.pipeline.transformers._apply_time_decay(order_date)
                    )

                    # Apply the same user ID and item ID prefixing as user/item sync
                    prefixed_user_id = self._get_prefixed_user_id(user_id, shop_id)
                    prefixed_item_id = self._get_prefixed_item_id(
                        str(product_id), shop_id
                    )

                    # Create feedback record
                    feedback = {
                        "feedback_type": "purchase",
                        "user_id": prefixed_user_id,
                        "item_id": prefixed_item_id,
                        "timestamp": order_date,
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": decayed_weight,
                                "order_id": order_id,
                                "quantity": quantity,
                                "line_total": line_total,
                                "total_order_value": total_amount,
                            }
                        ),
                    }

                    feedback_list.append(feedback)

                except Exception as item_error:
                    logger.error(f"Failed to process line item: {str(item_error)}")
                    logger.debug(f"Problematic line item: {item}")
                    continue

            if feedback_list:
                logger.debug(
                    f"Created {len(feedback_list)} purchase feedback records from order {order_id}"
                )

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to convert order to feedback: {str(e)}")
            logger.debug(f"Order data: {order}")
            return []

    def _deduplicate_feedback(
        self, feedback_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate feedback entries"""
        seen = set()
        unique_feedback = []

        for feedback in feedback_list:
            key = (
                feedback.get("user_id"),
                feedback.get("item_id"),
                feedback.get("feedback_type"),
                feedback.get("timestamp"),
            )
            if key not in seen:
                seen.add(key)
                unique_feedback.append(feedback)

        return unique_feedback
