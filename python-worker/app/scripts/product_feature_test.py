import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.domains.ml.feature_engineering.product_features.orchestrator import (
    ProductFeatureOrchestrator,
)


async def main(shop_id: str, product_id: str):
    """
    Main function to initialize DB and run the pipeline.
    """
    orchestrator = ProductFeatureOrchestrator(shop_id=shop_id)
    await orchestrator.run_pipeline_for_product(product_id=product_id)


if __name__ == "__main__":

    asyncio.run(main(shop_id="cmg7uepe70003v33u0m4scnad", product_id="7925260451979"))
