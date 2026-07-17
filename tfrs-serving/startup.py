#!/usr/bin/env python3
"""
Startup script for BentoML TFRS serving container.

Syncs models from OCI Object Storage to local filesystem,
then imports them into BentoML's model store for serving.
"""

import os
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_BASE_PATH = os.getenv("MODEL_BASE_PATH", "/models")
BENTOML_MODEL_STORE = os.getenv("BENTOML_HOME", "/home/bentoml/bentoml")


def sync_models_from_oci():
    """Download models from OCI Object Storage to local filesystem."""
    try:
        from oci_registry import OciModelRegistry
    except ImportError:
        logger.warning("OCI SDK not available, skipping OCI sync")
        return

    registry = OciModelRegistry(
        bucket_name=os.getenv("OCI_BUCKET", "betterbundle-tfrs-models"),
        use_instance_principal=os.getenv("OCI_USE_INSTANCE_PRINCIPAL", "true").lower()
        == "true",
    )

    try:
        # List shops that have models in OCI
        # For now, we'll try to download for each shop directory in local path
        # In production, you'd list from OCI
        logger.info("Checking for models to sync from OCI...")
        # This would be called per-shop when a request comes in for a shop without a local model
        logger.info("OCI sync available on-demand")
    except Exception as e:
        logger.warning(f"OCI sync failed (non-fatal): {e}")


def import_models_to_bentoml():
    """Import models from shared volume into BentoML model store."""
    import bentoml
    import tensorflow as tf

    model_base = os.getenv("MODEL_BASE_PATH", "/models")
    if not os.path.exists(model_base):
        logger.info(f"No model base path found at {model_base}")
        return

    for shop_id in os.listdir(model_base):
        shop_path = os.path.join(model_base, shop_id)
        if not os.path.isdir(shop_path):
            continue

        # Check if model already exists in BentoML store
        model_tag = f"betterbundle-tfrs-{shop_id}:latest"
        try:
            existing = bentoml.models.get(model_tag)
            logger.info(f"Model {model_tag} already in BentoML store")
            continue
        except bentoml.exceptions.NotFound:
            pass

        # Import model into BentoML store
        try:
            logger.info(f"Importing model for shop {shop_id} into BentoML store...")
            bentoml.tensorflow.save_model(
                f"betterbundle-tfrs-{shop_id}",
                tf.saved_model.load(shop_path),
                signatures={"serving_default": {"batchable": True, "batch_dim": 0}},
                labels={
                    "shop_id": shop_id,
                    "model_type": "two_tower_retrieval_ranking",
                },
            )
            logger.info(f"✅ Imported model for shop {shop_id}")
        except Exception as e:
            logger.error(f"Failed to import model for shop {shop_id}: {e}")


def main():
    logger.info("Starting BentoML TFRS serving container...")

    # Sync models from OCI (if configured)
    sync_models_from_oci()

    # Import models into BentoML model store
    import_models_to_bentoml()

    logger.info("Startup complete. Starting BentoML service...")


if __name__ == "__main__":
    main()
