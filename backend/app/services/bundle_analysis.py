"""
Bundle analysis service for the ML API
"""

from typing import List, Dict, Any, Optional
from prisma import Prisma
from app.models.requests import ProductData, OrderData
from app.models.responses import SimpleBundleAnalysisResponse
from app.core.logging import get_logger
from app.services.similarity_engine import SimilarityEngine
from app.services.data_processor import DataProcessor

logger = get_logger(__name__)


class BundleAnalysisService:
    """Service for bundle analysis operations"""

    def __init__(self):
        self.similarity_engine = SimilarityEngine()
        self.data_processor = DataProcessor()

    async def analyze_bundles_from_database(
        self, prisma: Prisma, shop_id: str
    ) -> SimpleBundleAnalysisResponse:
        """
        Analyze bundles using data from database

        Args:
            prisma: Prisma client instance
            shop_id: Shop identifier

        Returns:
            SimpleBundleAnalysisResponse with analysis results
        """
        try:
            logger.info(f"Starting bundle analysis for shop {shop_id}")

            # Get shop data
            shop = await prisma.shop.find_unique(where={"shopId": shop_id})
            if not shop:
                logger.error(f"Shop not found: {shop_id}")
                return SimpleBundleAnalysisResponse(
                    success=False, message=f"Shop not found: {shop_id}"
                )

            # Get products and orders from database
            products_db, orders_db = await self._fetch_shop_data(prisma, shop.id)

            if not products_db or not orders_db:
                logger.warning(f"No data found for shop {shop_id}")
                return SimpleBundleAnalysisResponse(
                    success=True, message="No data found for analysis"
                )

            # Convert to internal models
            products = self._convert_products(products_db)
            orders = self._convert_orders(orders_db)

            # Perform analysis
            analysis_results = await self._perform_analysis(products, orders)

            if not analysis_results["bundles"]:
                logger.warning(f"No bundles generated for shop {shop_id}")
                return SimpleBundleAnalysisResponse(
                    success=True,
                    message="Analysis completed but no bundles were generated",
                )

            # Save results to database
            bundles_saved = await self._save_bundles(
                prisma, shop.id, analysis_results["bundles"]
            )

            logger.info(
                f"Successfully saved {bundles_saved} bundles for shop {shop_id}"
            )

            return SimpleBundleAnalysisResponse(
                success=True,
                message=f"Bundle analysis completed successfully. Generated {bundles_saved} bundles.",
                bundles_generated=bundles_saved,
            )

        except Exception as e:
            logger.error(f"Error in bundle analysis for shop {shop_id}: {str(e)}")
            return SimpleBundleAnalysisResponse(
                success=False, message=f"Bundle analysis failed: {str(e)}"
            )

    async def _fetch_shop_data(
        self, prisma: Prisma, shop_db_id: str
    ) -> tuple[List, List]:
        """Fetch products and orders for a shop"""
        products_db = await prisma.productdata.find_many(
            where={"shopId": shop_db_id, "isActive": True}
        )

        orders_db = await prisma.orderdata.find_many(where={"shopId": shop_db_id})

        logger.info(f"Found {len(products_db)} products and {len(orders_db)} orders")

        # Debug: Show sample data
        if products_db:
            sample_product = products_db[0]
            logger.info(
                f"Sample product: ID={sample_product.productId}, Title={sample_product.title}, Price={sample_product.price}"
            )

        if orders_db:
            sample_order = orders_db[0]
            logger.info(
                f"Sample order: ID={sample_order.orderId}, Total={sample_order.totalAmount}, LineItems={len(sample_order.lineItems) if sample_order.lineItems else 0}"
            )

        return products_db, orders_db

    def _convert_products(self, products_db: List) -> List[ProductData]:
        """Convert database products to ProductData models"""
        products = []
        for product in products_db:
            products.append(
                ProductData(
                    product_id=product.productId,
                    title=product.title,
                    category=product.category,
                    price=product.price,
                    tags=product.tags if product.tags else [],
                    description="",  # Not stored in DB
                    image_url=product.imageUrl,
                )
            )
        return products

    def _convert_orders(self, orders_db: List) -> List[OrderData]:
        """Convert database orders to OrderData models"""
        orders = []
        for order in orders_db:
            # Transform line_items from GraphQL structure to simple list
            line_items = self.data_processor.transform_line_items(order.lineItems)

            orders.append(
                OrderData(
                    order_id=order.orderId,
                    customer_id=order.customerId,
                    total_amount=order.totalAmount,
                    order_date=order.orderDate.isoformat(),
                    line_items=line_items,
                )
            )
        return orders

    async def _perform_analysis(
        self, products: List[ProductData], orders: List[OrderData]
    ) -> Dict[str, Any]:
        """Perform the actual bundle analysis"""
        return self.similarity_engine.analyze_bundles(products, orders)

    async def _save_bundles(
        self, prisma: Prisma, shop_db_id: str, bundles: List[Dict[str, Any]]
    ) -> int:
        """Save bundles to database"""
        # Clear existing results
        await prisma.bundleanalysisresult.delete_many(where={"shopId": shop_db_id})

        # Prepare bundle data
        bundle_data = []
        for bundle in bundles:
            bundle_data.append(
                {
                    "shopId": shop_db_id,
                    "productIds": bundle["product_ids"],
                    "bundleSize": len(bundle["product_ids"]),
                    "coPurchaseCount": bundle["co_purchase_count"],
                    "confidence": bundle["confidence"],
                    "lift": bundle["lift"],
                    "support": bundle["support"],
                    "revenue": bundle.get("revenue_potential", 0),
                    "avgOrderValue": bundle.get("total_price", 0),
                    "discount": 0,
                    "isActive": True,
                }
            )

        # Save new results
        if bundle_data:
            await prisma.bundleanalysisresult.create_many(data=bundle_data)

        return len(bundle_data)
