# TFRS Production Serving Plan (OCI)

## Current Problem

The TFRS model runs **inside** the `python-worker` FastAPI process. This creates three critical issues:

1. **Event loop blocked**: `model(batch_features)` is a synchronous CPU-bound call inside `async def recommend()`. Every recommendation request blocks the event loop, freezing all other requests (health checks, billing, other shops).

2. **No separation of concerns**: The `python-worker` container carries TensorFlow (~1GB+), git-lfs, protobuf — all for one inference call per request. The 1GB memory limit in [`docker-compose.prod.yml:242`](docker-compose.prod.yml:242) is shared between API logic and ML inference.

3. **No model versioning**: Models are saved to a local `models/tfrs/<shop_id>/latest` directory that disappears on container restart. No rollback, no canary, no A/B.

---

## Target Architecture (OCI-Native)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OCI Region (ap-mumbai-1)                         │
│                                                                             │
│  ┌──────────────────────────────┐    ┌─────────────────────────────────┐   │
│  │  python-worker (FastAPI)     │    │  tfrs-inference (TF Serving)    │   │
│  │  ─────────────────────────── │    │  ─────────────────────────────── │   │
│  │  • Auth, sessions            │    │  • tensorflow/serving:2.18.0    │   │
│  │  • Recommendation logic      │───▶│  • Loads SavedModel per shop    │   │
│  │  • Exclusions, cache         │    │  • GPU-capable (A10/V100)       │   │
│  │  • LLM enrichment            │    │  • Request batching             │   │
│  │  • Training (batch job)      │    │  • Model version management     │   │
│  │  • NO TensorFlow import      │    │  • Reads from shared volume     │   │
│  └──────────────────────────────┘    └────────────┬────────────────────┘   │
│                                                    │                        │
│  ┌──────────────────────────────┐                   │                        │
│  │  OCI Object Storage Bucket  │◀──────────────────┘                        │
│  │  (betterbundle-tfrs-models)  │                                           │
│  │  ─────────────────────────── │                                           │
│  │  /models/<shop_id>/          │                                           │
│  │    ├── 1/  (saved_model.pb)  │                                           │
│  │    ├── 2/  (saved_model.pb)  │                                           │
│  │    └── latest → 2            │                                           │
│  │                             │                                           │
│  │  Lifecycle policy:           │                                           │
│  │  - Keep last 5 versions     │                                           │
│  │  - Delete versions >30 days │                                           │
│  └──────────────────────────────┘                                           │
│                                                    │                        │
│  ┌──────────────────────────────┐                   │                        │
│  │  pgvector (cold-start        │◀──────────────────┘                        │
│  │  fallback)                   │    When TF Serving is unavailable or      │
│  │  product_features.embedding  │    model not yet trained                  │
│  └──────────────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Separate TF Serving Container

**1.1 Fix model export format** — [`trainer.py`](python-worker/app/recommandations/tfrs/trainer.py:495)

Current `_get_model_path()` saves to `models/tfrs/<shop_id>/latest`. Change to versioned:

```python
def _get_model_path(self, shop_id: str, version: Optional[str] = None) -> str:
    version = version or str(int(time.time()))
    base = os.getenv("TFRS_MODEL_PATH", self.config.model_base_path)
    return os.path.join(base, shop_id, version)
```

After saving, update a `latest` symlink and upload to OCI.

**1.2 Add `tfrs-inference` service** to [`docker-compose.prod.yml`](docker-compose.prod.yml)

```yaml
tfrs-inference:
  image: tensorflow/serving:2.18.0-gpu
  container_name: betterbundle-tfrs-inference
  volumes:
    - tfrs_models:/models # shared volume with python-worker
    - ./infrastructure/tf-serving-config:/config # model config
  environment:
    - MODEL_NAME=tfrs
    - MODEL_BASE_PATH=/models
    - TF_CPP_VLOG_LEVEL=0
    - NUM_SERVERS_PER_MODEL=1
    - NUM_GPU=0 # set to 1 if GPU available
    - OCI_CONFIG_FILE=/etc/oci/config # for model sync
  ports:
    - "8501:8501" # REST API
    - "8500:8500" # gRPC API (preferred, faster)
  networks:
    - backend
  deploy:
    resources:
      limits:
        cpus: "2.0"
        memory: 2G
```

For local dev, use CPU image `tensorflow/serving:2.18.0` (non-gpu tag).

**1.3 Add shared model volume**

```yaml
volumes:
  tfrs_models: # shared between python-worker (rw) and tfrs-inference (ro)
```

Mount in both containers. python-worker writes during training; tfrs-inference reads for serving.

---

### Phase 2: OCI Object Storage Integration

**2.1 OCI SDK dependency** — add to [`requirements.txt`](python-worker/requirements.txt)

```
oci>=2.130.0
```

The [`infrastructure/scripts/create-oci-instance.sh`](infrastructure/scripts/create-oci-instance.sh) already uses OCI CLI. For Python, use the official [`oci`](https://pypi.org/project/oci/) SDK.

**2.2 Upload models after training** — add to [`TfrsTrainer.train_for_shop()`](python-worker/app/recommandations/tfrs/trainer.py:134)

```python
from app.infrastructure.oci import ObjectStorageClient

oci = ObjectStorageClient()
version = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
oci.upload_model(
    shop_id=shop_id,
    version=version,
    local_path=model_path,
)
oci.update_latest_symlink(shop_id, version)
```

**2.3 OCI Object Storage client** — new file: [`python-worker/app/infrastructure/oci/client.py`](python-worker/app/infrastructure/oci/client.py)

```python
import oci
from oci.object_storage import ObjectStorageClient

class OciModelRegistry:
    """Upload/download TFRS models from OCI Object Storage."""

    def __init__(self):
        # Use instance principal auth (no API key needed on OCI compute)
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        self.client = ObjectStorageClient(config={}, signer=signer)
        self.bucket_name = "betterbundle-tfrs-models"
        self.namespace = self.client.get_namespace().data

    def upload_model(self, shop_id: str, version: str, local_path: str):
        """Upload SavedModel directory to OCI Object Storage."""
        for root, dirs, files in os.walk(local_path):
            for f in files:
                full_path = os.path.join(root, f)
                object_name = f"models/{shop_id}/{version}/{os.path.relpath(full_path, local_path)}"
                with open(full_path, "rb") as data:
                    self.client.put_object(
                        namespace_name=self.namespace,
                        bucket_name=self.bucket_name,
                        object_name=object_name,
                        put_object_body=data,
                    )

    def download_model(self, shop_id: str, version: str, dest_path: str):
        """Download model from OCI to local filesystem (used on container startup)."""
        objects = self.client.list_objects(
            namespace_name=self.namespace,
            bucket_name=self.bucket_name,
            prefix=f"models/{shop_id}/{version}/",
        )
        for obj in objects.data.objects:
            local_file = os.path.join(dest_path, os.path.relpath(obj.name, f"models/{shop_id}/{version}/"))
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            response = self.client.get_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=obj.name,
            )
            with open(local_file, "wb") as f:
                for chunk in response.data.raw.stream(1024 * 1024, decode_content=False):
                    f.write(chunk)
```

**2.4 Model sync on TF Serving startup** — new init script

```bash
# infrastructure/scripts/sync-tfrs-models.sh
#!/bin/bash
# Downloads latest TFRS models from OCI to shared volume on container startup

BUCKET="betterbundle-tfrs-models"
MOUNT_PATH="/models"

# List all shops that have models
oci os object list -bn "$BUCKET" --prefix "models/" --fields "name" | \
  jq -r '.data[] | select(.name | endswith("latest")) | .name' | \
  while read -r path; do
    shop_id=$(echo "$path" | cut -d'/' -f2)
    oci os object restore -bn "$BUCKET" --name "$path"
    # Download the version that 'latest' points to
    version=$(oci os object head -bn "$BUCKET" --name "$path" | jq -r '."opc-meta-version"')
    oci os object sync -bn "$BUCKET" --prefix "models/$shop_id/$version/" --dest "$MOUNT_PATH/$shop_id/$version/"
  done
```

**2.5 OCI resource configuration**

- **Bucket**: `betterbundle-tfrs-models` (standard tier, auto-tiers to infrequent after 30 days)
- **Lifecycle**: Keep last 5 versions per shop, delete versions older than 90 days
- **Auth**: Use [instance principals](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/callingservicesfrominstances.htm) — no API keys in environment variables. The OCI compute instance gets a dynamic group with policy to read/write the bucket.

```hcl
# OCI IAM Policy
Allow dynamic-group BetterBundleCompute to manage objects in compartment Marketing where target.bucket.name = 'betterbundle-tfrs-models'
```

---

### Phase 3: Refactor python-worker to Remove In-Process TFRS

**3.1 Create TF Serving client** — new file: [`python-worker/app/recommandations/tfrs/serving_client.py`](python-worker/app/recommandations/tfrs/serving_client.py)

```python
import httpx
import json

class TfServingClient:
    """HTTP client for TF Serving REST API."""

    def __init__(self, base_url: str = "http://tfrs-inference:8501"):
        self.base_url = base_url
        self.http = httpx.AsyncClient(timeout=30.0)

    async def predict(
        self, shop_id: str, model_version: str, instances: list
    ) -> list:
        """
        Send predict request to TF Serving.

        TF Serving REST API:
        POST /v1/models/tfrs/versions/<version>:predict
        """
        resp = await self.http.post(
            f"{self.base_url}/v1/models/tfrs/versions/{model_version}:predict",
            json={"instances": instances},
        )
        resp.raise_for_status()
        return resp.json()["predictions"]
```

**3.2 Update [`TfrsServing.recommend()`](python-worker/app/recommandations/tfrs/serving.py:34)**

Replace in-process `model(batch_features)` with an HTTP call:

```python
# Before (blocks event loop, requires TF in process):
scores = model(batch_features)

# After (async HTTP to TF Serving, no TF in api process):
scores = await self.tf_serving_client.predict(
    shop_id=shop_id,
    model_version=self._get_model_version(shop_id),
    instances=batch_features,
)
```

**3.3 Remove TensorFlow from python-worker**

- Remove `tensorflow` and `tensorflow-recommenders` from [`requirements.txt`](python-worker/requirements.txt)
- Keep TFRS model _code_ in the repo (for training, which runs as a separate batch job)
- Add `httpx` and `oci` to requirements
- The `python-worker` container shrinks from ~1.8GB to ~300MB

---

### Phase 4: Training Pipeline Isolation

**4.1 Move training out of request path**

Training is already triggered by the Kafka consumer [`feature_computation_consumer.py`](python-worker/app/consumers/kafka/feature_computation_consumer.py:113). This is correct — it runs as a background task. But it currently runs in the same container as HTTP serving.

**Fix**: Run training in the python-worker container but:

- Use a separate subprocess via `asyncio.create_subprocess_exec` to avoid memory pressure on the main process
- Kill training if it exceeds 30 minutes (timeout)
- Send results to OCI after completion

**4.2 Training metrics to track**

```python
# Prometheus-style metrics (can be exported via OpenTelemetry)
tfrs_training_duration_seconds{shop_id="...", status="success"} 124.5
tfrs_training_last_success_timestamp{shop_id="..."} 1700000000
tfrs_inference_latency_seconds{shop_id="..."} 0.042
tfrs_model_version{shop_id="...", version="20240715-123000"} 1
```

---

## Files to Create/Modify

### New files

| File                                                       | Purpose                                               |
| ---------------------------------------------------------- | ----------------------------------------------------- |
| `python-worker/app/infrastructure/oci/__init__.py`         | OCI module init                                       |
| `python-worker/app/infrastructure/oci/client.py`           | OCI Object Storage client for model registry          |
| `python-worker/app/recommandations/tfrs/serving_client.py` | HTTP client for TF Serving REST/gRPC API              |
| `infrastructure/scripts/sync-tfrs-models.sh`               | Sync latest models from OCI to TF Serving on startup  |
| `infrastructure/tf-serving-config/models.config`           | TF Serving model config file (lists available models) |

### Modified files

| File                                                                                                     | Change                                                         |
| -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| [`python-worker/app/recommandations/tfrs/trainer.py`](python-worker/app/recommandations/tfrs/trainer.py) | Versioned model paths + OCI upload after training              |
| [`python-worker/app/recommandations/tfrs/serving.py`](python-worker/app/recommandations/tfrs/serving.py) | Replace inline `model()` call with `TfServingClient.predict()` |
| [`python-worker/requirements.txt`](python-worker/requirements.txt)                                       | Remove TF/TFRS, add `oci>=2.130.0`, `httpx`                    |
| [`python-worker/Dockerfile.prod`](python-worker/Dockerfile.prod)                                         | Remove TF build deps (gcc/g++ no longer needed)                |
| [`docker-compose.prod.yml`](docker-compose.prod.yml)                                                     | Add `tfrs-inference` service + `tfrs_models` volume            |
| [`docker-compose.dev.yml`](docker-compose.dev.yml)                                                       | Add `tfrs-inference` service for local dev                     |
| [`docker-compose.local.yml`](docker-compose.local.yml)                                                   | Add `tfrs-inference` service for local dev                     |
| [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py)                 | Add OCI config (bucket name, namespace)                        |

---

## OCI-Specific Considerations

### Authentication

| Environment        | Auth method         | How                                           |
| ------------------ | ------------------- | --------------------------------------------- |
| OCI Compute (prod) | Instance principals | Automatic — no keys needed                    |
| Local dev          | API key             | `~/.oci/config` or env vars `OCI_CONFIG_FILE` |

### Instance principal setup

1. Create a **dynamic group** matching your compute instances:

```
ALL {instance.compartment.id = 'ocid1.compartment.oc1..<value>'}
```

2. Create a policy granting object storage access:

```
Allow dynamic-group BetterBundleCompute to manage objects in compartment BetterBundle where target.bucket.name = 'betterbundle-tfrs-models'
```

### OCI Object Storage vs S3-compatible API

OCI Object Storage supports both:

- **Native OCI API** (via `oci` SDK) — used for upload/download in Python
- **S3-compatible API** — could use `boto3` with OCI endpoint, but `oci` SDK is preferred for instance principal auth

### Cost

OCI Object Storage standard tier:

- Storage: ~$0.025/GB/month
- Each model version is ~50-200MB
- 100 shops × 5 versions × 100MB = 50GB → ~$1.25/month
- Requests: negligible at this scale

---

## Decision Matrix

| Scenario                                | Recommended approach                                                                                                                                |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| < 10 shops, cold-start is main use case | **pgvector only** — skip TF Serving entirely. The Vertex AI embeddings already in `product_features.embedding` + co-purchase boosting handles this. |
| 10-100 shops, need personalization      | **TF Serving** — separate container, OCI model registry. Worth the infra.                                                                           |
| > 100 shops                             | **TF Serving + model version pruning** — only keep last 3 versions per shop. Consider pgvector as primary with TFRS as re-ranking layer.            |
| No GPU available                        | **TF Serving CPU** — slow but works. Or **pgvector only**.                                                                                          |

---

## Open Questions

Before starting implementation, answer:

1. **Do you have GPU compute in OCI?** (A10, V100, or just Ampere A1 CPU?)

   - The [`create-oci-instance.sh`](infrastructure/scripts/create-oci-instance.sh) uses `VM.Standard.A1.Flex` (Ampere CPU) — no GPU. TF Serving on CPU is slow for per-request inference.
   - **If no GPU → pgvector-only is dramatically simpler and likely sufficient.**

2. **How many shops are active now, and how many will have TFRS models?**

   - If < 20, TF Serving overhead isn't justified.

3. **Do you need per-user personalized recommendations, or is "similar products" enough?**
   - pgvector: semantic similarity (product-to-product)
   - TFRS: learned user embedding (user-to-product)
   - Most Shopify apps work fine with product similarity + frequency boosting.
