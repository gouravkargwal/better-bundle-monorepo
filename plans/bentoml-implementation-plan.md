# BentoML + TFRS Implementation Plan

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          docker-compose                                  │
│                                                                          │
│  ┌────────────────────────────┐    ┌───────────────────────────────┐    │
│  │  python-worker (FastAPI)   │    │  bentoml-serving               │    │
│  │  ───────────────────────── │    │  ───────────────────────────── │    │
│  │  • Auth, sessions          │    │  • BentoML auto-generated API  │    │
│  │  • Recommendation logic    │───▶│  • Loads TFRS SavedModel       │    │
│  │  • Exclusions, cache       │HTTP│  • REST/gRPC endpoint          │    │
│  │  • LLM enrichment          │    │  • Async inference             │    │
│  │  • NO TensorFlow import    │    │  • Prometheus metrics          │    │
│  │  • BentoML client (httpx)  │    │  • GPU-capable                 │    │
│  └────────────────────────────┘    └──────────────┬─────────────────┘    │
│                                                   │                       │
│  ┌────────────────────────────┐                   │                       │
│  │  BentoML Model Registry    │◀──────────────────┘                       │
│  │  (on shared volume)        │   bentoml save writes here                │
│  │  /bentoml/models/          │   bentoml serve reads from here           │
│  └────────────────────────────┘                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Files to Create

### 1. `python-worker/bentoml_service/service.py`

BentoML service that loads the TFRS model and exposes a predict endpoint.

### 2. `python-worker/bentoml_service/bentofile.yaml`

BentoML build configuration.

### 3. `python-worker/bentoml_service/Dockerfile.bentoml`

Multi-stage Dockerfile for the BentoML serving container.

### 4. `python-worker/app/recommandations/tfrs/serving_client.py`

Async HTTP client that calls the BentoML service from python-worker.

## Files to Modify

| File                                                | Change                                                                 |
| --------------------------------------------------- | ---------------------------------------------------------------------- |
| `python-worker/app/recommandations/tfrs/trainer.py` | Add `bentoml.tensorflow.save_model()` after training                   |
| `python-worker/app/recommandations/tfrs/serving.py` | Replace `model()` call with `BentoMLClient.predict()`                  |
| `python-worker/requirements.txt`                    | Add `bentoml`, `httpx`; remove `tensorflow`, `tensorflow-recommenders` |
| `python-worker/Dockerfile.prod`                     | Remove TF build deps (gcc/g++ no longer needed)                        |
| `docker-compose.dev.yml`                            | Add `bentoml-serving` service                                          |
| `docker-compose.local.yml`                          | Add `bentoml-serving` service                                          |
| `docker-compose.prod.yml`                           | Add `bentoml-serving` service + shared volume                          |

---

## Detailed Todo Items

### Todo 1: Install BentoML and save TFRS model after training

**File**: [`python-worker/app/recommandations/tfrs/trainer.py`](python-worker/app/recommandations/tfrs/trainer.py)

Add this import and one line after `model.fit()` completes:

```python
# After training completes, around line 130
import bentoml

history = model.fit(train_ds, epochs=..., validation_data=eval_ds, callbacks=[early_stop])

# Save to BentoML model registry
bentoml.tensorflow.save_model(
    "betterbundle-tfrs",
    model,
    signatures={
        "serving_default": {"batchable": True, "batch_dim": 0},
    },
    labels={
        "shop_id": shop_id,
        "model_type": "two_tower_retrieval_ranking",
    },
    metadata={
        "final_loss": float(history.history["total_loss"][-1]),
        "training_examples": len(train_df),
        "epochs_trained": len(history.history["total_loss"]),
    },
)
```

This saves the model to `~/bentoml/models/betterbundle-tfrs/<version>/` on the shared volume.

**Also**: Add `bentoml` to [`python-worker/requirements.txt`](python-worker/requirements.txt):

```
bentoml>=1.3.0
```

### Todo 2: Create BentoML service definition

**New file**: `python-worker/bentoml_service/service.py`

```python
"""
BentoML service for BetterBundle TFRS recommendation model.
Loaded by the bentoml-serving container to serve predictions.
"""
import numpy as np
import bentoml
from bentoml.io import JSON, NumpyNdarray

# Load the latest model
model_ref = bentoml.models.get("betterbundle-tfrs:latest")
runner = bentoml.tensorflow.get_runner(model_ref)

svc = bentoml.Service(
    name="betterbundle-tfrs",
    runners=[runner],
)

@svc.api(input=JSON(), output=JSON())
async def predict(input_data: dict) -> dict:
    """
    Predict recommendation scores for a batch of (user, product) pairs.

    Expected input:
    {
        "features": {
            "user_id": ["user_1", "user_2"],
            "product_id": ["prod_1", "prod_2"],
            "total_purchases": [3, 0],
            "lifetime_value": [150.0, 0.0],
            "text_embedding": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
            ...
        }
    }

    Returns:
    {
        "scores": [0.85, 0.32],
        "user_embeddings": [[...], [...]],
        "item_embeddings": [[...], [...]]
    }
    """
    result = await runner.predict.async_run(input_data["features"])
    return {
        "scores": result["score"].tolist(),
        "user_embeddings": result["user_embedding"].tolist(),
        "item_embeddings": result["item_embedding"].tolist(),
    }
```

### Todo 3: Create BentoML build config

**New file**: `python-worker/bentoml_service/bentofile.yaml`

```yaml
service: "service.py:svc"
include:
  - "service.py"
python:
  packages:
    - tensorflow==2.18.0
    - tensorflow-recommenders==0.7.3
    - numpy>=1.26.0
docker:
  python_version: "3.11"
  cuda_version: "12.4.0" # Omit this line for CPU-only
  system_packages:
    - curl
```

### Todo 4: Add bentoml-serving container to docker-compose

**Files**: `docker-compose.dev.yml`, `docker-compose.local.yml`, `docker-compose.prod.yml`

```yaml
bentoml-serving:
  build:
    context: ./python-worker/bentoml_service
    dockerfile: Dockerfile.bentoml
  container_name: betterbundle-bentoml
  ports:
    - "3001:3000" # BentoML default port
  volumes:
    - bentoml_models:/home/bentoml/bentoml/models # shared with python-worker
  environment:
    - BENTOML_PORT=3000
  networks:
    - backend
  restart: unless-stopped
  depends_on:
    python-worker:
      condition: service_started
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
```

Also add the shared volume:

```yaml
volumes:
  bentoml_models:
```

And mount it in the `python-worker` service too:

```yaml
python-worker:
  volumes:
    - bentoml_models:/app/bentoml/models
```

### Todo 5: Create BentoML client in python-worker

**New file**: `python-worker/app/recommandations/tfrs/serving_client.py`

```python
"""
Async HTTP client for BentoML serving.
Replaces in-process TensorFlow inference with remote call.
"""
import httpx
from typing import Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class BentoMLClient:
    """Async client for BentoML TFRS serving."""

    def __init__(self, base_url: str = "http://bentoml-serving:3000"):
        self.base_url = base_url
        self.http = httpx.AsyncClient(timeout=60.0)

    async def predict(
        self, features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send batch features to BentoML for scoring.

        Args:
            features: Dict of feature arrays (same structure as model expects)

        Returns:
            Dict with scores, user_embeddings, item_embeddings
        """
        try:
            resp = await self.http.post(
                f"{self.base_url}/predict",
                json={"features": features},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            logger.error("BentoML serving request timed out")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"BentoML serving returned {e.response.status_code}: {e.response.text}")
            raise
```

### Todo 6: Update TfrsServing to use BentoML client

**File**: [`python-worker/app/recommandations/tfrs/serving.py`](python-worker/app/recommandations/tfrs/serving.py)

```python
# Replace this in recommend() method around line 86:

# Before (synchronous, blocks event loop, requires TF in process):
scores = model(batch_features)

# After (async HTTP to BentoML, no TF in api process):
scores_response = await self.bentoml_client.predict(batch_features)
all_scores = scores_response["scores"]
```

Also update `__init__` to initialize the client:

```python
from .serving_client import BentoMLClient

class TfrsServing:
    def __init__(self, config: Optional[TfrsConfig] = None):
        self.config = config or TfrsConfig()
        self.features = FeatureTransformer(self.config)
        self.bentoml_client = BentoMLClient()
        self._models: Dict[str, tf.saved_model] = {}  # fallback cache
        ...
```

### Todo 7: Remove TensorFlow from python-worker

**File**: [`python-worker/requirements.txt`](python-worker/requirements.txt)

Remove:

```
tensorflow==2.18.0
tensorflow-recommenders==0.7.3
```

Add:

```
bentoml>=1.3.0
httpx>=0.27.0
```

**File**: [`python-worker/Dockerfile.prod`](python-worker/Dockerfile.prod)

Remove gcc/g++ system deps (they're only needed to compile TF):

```dockerfile
# Remove or comment out:
# RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*
```

TensorFlow is a C++ heavy build. Without TF, the container build goes from 5-10 minutes to ~30 seconds.

---

## Runtime Flow (after all changes)

```
1. Training triggered (Kafka consumer)
   → TfrsScheduler.train_shop(shop_id)
   → TfrsTrainer.train_for_shop(shop_id)
   → model.fit(...)  ← TensorFlow still runs here (training container)
   → bentoml.tensorflow.save_model(...)  ← saves to shared volume
   → BentoML auto-picks up new version

2. Recommendation request comes in
   → python-worker handles auth, sessions, exclusions, cache
   → TfrsServing.recommend(...)
   → BentoMLClient.predict(batch_features)  ← async HTTP call
   → bentoml-serving processes on its own (potentially GPU)
   → Returns scores → python-worker enriches + returns

3. No TensorFlow in FastAPI process
   → python-worker is lightweight (no TF memory overhead)
   → Event loop never blocked by model inference
   → HTTP timeout handles serving failures gracefully
   → Fallback to pgvector or popular if BentoML is down
```

## Rollout Order

```
Step 1: Add bentoml + httpx to requirements.txt (no TF removal yet)
Step 2: Create service.py + bentofile.yaml for BentoML
Step 3: Add bentoml-serving to docker-compose files
Step 4: Add one line to trainer.py to save model via BentoML
Step 5: Test that bentoml-serving loads and serves correctly
Step 6: Create BentoMLClient + update TfrsServing to use it
Step 7: Test end-to-end with bentoml-serving
Step 8: Remove tensorflow from python-worker requirements
Step 9: Remove gcc/g++ from Dockerfile.prod
```

Each step is reversible. If something breaks at step 5, you still have the old inline TFRS path working.
