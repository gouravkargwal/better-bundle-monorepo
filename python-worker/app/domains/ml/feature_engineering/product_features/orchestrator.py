from app.core.logging import get_logger
from .data_fetcher import DataFetcher

# from .feature_computer import FeatureComputer
# from .feature_saver import FeatureSaver

logger = get_logger(__name__)


class ProductFeatureOrchestrator:
    """
    Orchestrates the entire process of fetching data, computing features,
    and saving them for the product feature table.
    """

    def __init__(self, shop_id: str):
        self.shop_id = shop_id
        self.data_fetcher = DataFetcher(shop_id)
        # self.feature_computer = FeatureComputer()
        # self.feature_saver = FeatureSaver()

    async def run_pipeline_for_product(self, product_id: str):
        """
        Runs the full feature engineering pipeline for a single product.
        """
        try:
            # Step 1: Fetch the necessary data
            logger.info(f"Fetching data for product: {product_id}")
            raw_data = await self.data_fetcher.fetch_data_for_product(product_id)
            logger.info(f"Raw data fetched successfully: {raw_data}")
            # Step 2: Compute the features
            logger.info(f"Computing features for product: {product_id}")
            # computed_features = self.feature_computer.compute(raw_data, context)

            # Step 3: Save the features
            logger.info(f"Saving features for product: {product_id}")
            # await self.feature_saver.save(computed_features)

            logger.info(f"Successfully processed product: {product_id}")

        except Exception as e:
            logger.error(f"Failed to process product {product_id}: {str(e)}")
            # You can add more robust error handling here, like sending to a DLQ
