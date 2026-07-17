"""
OCI Object Storage model registry for TFRS SavedModels.

Handles upload/download of trained models to/from OCI Object Storage.
- Production: uses instance principal auth (no keys needed)
- Local dev: uses API key from ~/.oci/config or env vars

Bucket structure:
  betterbundle-tfrs-models/
    models/<shop_id>/
      latest       ← symlink object pointing to current version
      <version>/   ← actual model files (saved_model.pb, variables/, assets/)
"""

import os
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OciModelRegistry:
    """Upload/download TFRS models from OCI Object Storage."""

    def __init__(
        self,
        bucket_name: str = "betterbundle-tfrs-models",
        namespace: Optional[str] = None,
        use_instance_principal: bool = True,
    ):
        self.bucket_name = bucket_name
        self._client = None
        self._namespace = namespace
        self._use_instance_principal = use_instance_principal

    def _get_client(self):
        """Lazy-init the OCI Object Storage client."""
        if self._client is not None:
            return self._client

        import oci

        try:
            if self._use_instance_principal:
                # On OCI compute — no keys required
                signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
                self._client = oci.object_storage.ObjectStorageClient(
                    config={}, signer=signer
                )
                logger.info("OCI client initialized with instance principal auth")
            else:
                # Local dev — uses ~/.oci/config
                self._client = oci.object_storage.ObjectStorageClient(
                    config=oci.config.from_file()
                )
                logger.info("OCI client initialized with config file auth")

            # Cache namespace
            if not self._namespace:
                self._namespace = self._client.get_namespace().data
                logger.info(f"OCI namespace: {self._namespace}")

            return self._client
        except Exception as e:
            logger.error(f"Failed to initialize OCI client: {e}")
            raise

    def upload_model(self, shop_id: str, local_path: str) -> str:
        """
        Upload a SavedModel directory to OCI Object Storage.

        Args:
            shop_id: Shop identifier (used as prefix in bucket).
            local_path: Local filesystem path to the SavedModel directory.

        Returns:
            Version string (timestamp-based) that was uploaded.
        """
        client = self._get_client()
        version = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        prefix = f"models/{shop_id}/{version}"
        uploaded = 0

        for root, dirs, files in os.walk(local_path):
            for filename in files:
                full_path = os.path.join(root, filename)
                # Compute object name relative to local_path
                rel_path = os.path.relpath(full_path, local_path)
                object_name = f"{prefix}/{rel_path}"

                with open(full_path, "rb") as data:
                    self._get_client().put_object(
                        namespace_name=self._namespace,
                        bucket_name=self.bucket_name,
                        object_name=object_name,
                        put_object_body=data,
                    )
                    uploaded += 1

        logger.info(f"Uploaded {uploaded} files for shop {shop_id} version {version}")

        # Upload 'latest' pointer object (small text file with version)
        client = self._get_client()
        client.put_object(
            namespace_name=self._namespace,
            bucket_name=self.bucket_name,
            object_name=f"models/{shop_id}/latest",
            put_object_body=version.encode(),
            opc_meta={"version": version},
        )

        return version

    def download_model(
        self, shop_id: str, dest_path: str, version: Optional[str] = None
    ) -> str:
        """
        Download a model from OCI to local filesystem.

        Args:
            shop_id: Shop identifier.
            dest_path: Local directory to download into.
            version: Specific version to download. If None, resolves 'latest'.

        Returns:
            The version that was downloaded.
        """
        client = self._get_client()

        # Resolve version
        if version is None:
            version = self._resolve_latest(shop_id)
            if not version:
                raise FileNotFoundError(
                    f"No model found for shop {shop_id} in OCI bucket"
                )

        prefix = f"models/{shop_id}/{version}/"
        model_dir = os.path.join(dest_path, shop_id)
        os.makedirs(model_dir, exist_ok=True)

        downloaded = 0
        objects = client.list_objects(
            namespace_name=self._namespace,
            bucket_name=self.bucket_name,
            prefix=prefix,
        )

        for obj in objects.data.objects:
            # Strip the prefix to get relative path
            rel_path = obj.name[len(prefix) :]
            local_file = os.path.join(model_dir, rel_path)
            os.makedirs(os.path.dirname(local_file), exist_ok=True)

            response = client.get_object(
                namespace_name=self._namespace,
                bucket_name=self.bucket_name,
                object_name=obj.name,
            )
            with open(local_file, "wb") as f:
                for chunk in response.data.raw.stream(
                    1024 * 1024, decode_content=False
                ):
                    f.write(chunk)
            downloaded += 1

        logger.info(
            f"Downloaded {downloaded} files for shop {shop_id} version {version}"
        )
        return version

    def _resolve_latest(self, shop_id: str) -> Optional[str]:
        """Get the version string from the 'latest' pointer object."""
        client = self._get_client()
        try:
            response = client.get_object(
                namespace_name=self._namespace,
                bucket_name=self.bucket_name,
                object_name=f"models/{shop_id}/latest",
            )
            return response.data.text.strip()
        except Exception:
            logger.warning(f"No 'latest' pointer found for shop {shop_id}")
            return None

    def list_versions(self, shop_id: str) -> list:
        """List available model versions for a shop."""
        client = self._get_client()
        objects = client.list_objects(
            namespace_name=self._namespace,
            bucket_name=self.bucket_name,
            prefix=f"models/{shop_id}/",
            delimiter="/",
        )
        # Extract version directories from common prefixes
        versions = []
        for prefix in objects.data.prefixes or []:
            # prefix is like "models/<shop_id>/<version>/"
            parts = prefix.strip("/").split("/")
            if len(parts) >= 3:
                versions.append(parts[2])
        return sorted(set(versions))
