# ML Serving Frameworks Comparison

## The question: "Is there a framework to manage this easily rather than doing everything from scratch?"

**Yes.** There are several mature frameworks that handle model serving, versioning, registry, scaling, and monitoring — without you building custom OCI upload scripts, TF Serving configs, or sync containers.

---

## Top Contenders

### 1. BentoML ⭐ (Recommended for this use case)

[ bentoml.com](https://bentoml.com) — Open source (Apache 2.0)

**What it does**: Package → Serve → Deploy → Monitor. One framework from training to production.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  train.py    │───▶│  bentoml      │───▶│  BentoML     │───▶│  Docker/OCI   │
│  (your code) │    │  save()      │    │  API Server  │    │  /Kubernetes  │
│              │    │               │    │  (REST/gRPC) │    │  Deployment   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                           │
                    ┌──────┴──────┐
                    │  Model       │
                    │  Registry    │
                    │  (BentoCloud │
                    │   or local)  │
                    └─────────────┘
```

**How it fits BetterBundle's TFRS:**

```python
# Instead of writing a TF Serving client, OCI uploader, sync script...
# You do this:

import bentoml
import tensorflow_recommenders as tfrs

# After training:
bentoml.tensorflow.save_model(
    "betterbundle-tfrs",
    model,
    signatures={"predict": {"batchable": True, "batch_dim": 0}},
    labels={"shop_id": shop_id, "version": version},
)

# The serving part — BentoML auto-generates a REST/gRPC API:
# service.py
import bentoml
from bentoml.io import JSON

model_ref = bentoml.models.get("betterbundle-tfrs:latest")
runner = bentoml.tensorflow.get_runner(model_ref)

svc = bentoml.Service(name="tfrs-recommendation", runners=[runner])

@svc.api(input=JSON(), output=JSON())
async def recommend(batch: dict) -> dict:
    predictions = await runner.predict.async_run(batch["instances"])
    return {"predictions": predictions.tolist()}
```

| Capability       | BentoML                                    | Building from scratch                            |
| ---------------- | ------------------------------------------ | ------------------------------------------------ |
| Model packaging  | `bentoml.save()`                           | Manually organize SavedModel directory           |
| REST/gRPC API    | Auto-generated                             | Build Flask/FastAPI endpoint + TF Serving client |
| Model registry   | Built-in (BentoCloud or self-hosted Yatai) | OCI Object Storage + manual versioning           |
| Containerization | `bentoml containerize`                     | Write Dockerfile for TF Serving                  |
| GPU scheduling   | Built-in                                   | Manual `CUDA_VISIBLE_DEVICES`                    |
| Monitoring       | Prometheus metrics auto-exported           | Build custom metrics                             |
| A/B testing      | Built-in traffic splitting                 | Custom router                                    |
| Auto-scaling     | Built-in (on Kubernetes)                   | Manual                                           |
| Python-native    | Yes — no TF Serving protocol needed        | Must learn TF Serving REST/gRPC API              |

**OCI deployment**: `bentoml deploy . --platform docker --registry oci.io/your-registry` — or use bentoml's built-in deploy to any Docker host.

**Best for**: Your exact situation — small team, existing TFRS model, want production serving without building infra.

---

### 2. MLflow

[ mlflow.org](https://mlflow.org) — Open source (Apache 2.0)

**What it does**: Experiment tracking → Model registry → Serving.

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  MLflow Tracking │───▶│  MLflow Registry │───▶│  MLflow Serving  │
│  (log params,    │    │  (version models,│    │  (REST API)      │
│   metrics,       │    │   stage: staging │    │   /              │
│   artifacts)     │    │   → production)  │    │  pyfunc serving  │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

```python
import mlflow.tensorflow

# Log model
mlflow.tensorflow.log_model(
    model, artifact_path="tfrs_model",
    registered_model_name="BetterBundleTFRS"
)

# Serve (CLI)
# mlflow models serve -m "models:/BetterBundleTFRS/production" --port 5001
```

**Pros**: Great for experiment tracking. Model registry with staging/promotion. Lightweight.
**Cons**: Serving is basic — single-process, no GPU scheduling, no auto-scaling. You'd still need something else for production serving.

**Best for**: Experiment tracking + model registry, but you'd pair it with TF Serving or BentoML for actual serving.

---

### 3. Ray Serve

[ docs.ray.io/en/latest/serve](https://docs.ray.io/en/latest/serve/) — Open source (Apache 2.0)

**What it does**: Distributed serving with autoscaling, batching, and multi-model composition.

```python
from ray import serve
import tensorflow as tf

@serve.deployment(num_replicas=2, ray_actor_options={"num_gpus": 0.5})
class TfrsDeployment:
    async def __init__(self):
        self.model = tf.saved_model.load("/models/tfrs/latest")

    async def __call__(self, request):
        return self.model(request)

serve.run(TfrsDeployment.bind())
```

**Pros**: Native async, distributed, autoscaling, multi-model composition (chain models).
**Cons**: Requires Ray cluster. Overkill for <10 models. Another infrastructure component.

**Best for**: High-throughput, multi-model pipelines needing autoscaling.

---

### 4. KServe (formerly KFServing)

[ kserve.github.io](https://kserve.github.io) — Open source (Apache 2.0) — CNCF incubating

**What it does**: Kubernetes-native model serving. Supports TF Serving, Triton, MLServer, PyTorch, etc.

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: tfrs-recommendation
spec:
  predictor:
    tensorflow:
      storageUri: oci://betterbundle-tfrs-models/models/shop_123/
      resources:
        limits:
          nvidia.com/gpu: 1
```

**Pros**: Declarative (YAML), built-in canary, metrics, autoscaling. Uses TF Serving under the hood.
**Cons**: Requires Kubernetes. You need a K8s cluster on OCI (OKE — Oracle Kubernetes Engine).

**Best for**: Teams already on Kubernetes. Since you're on OCI with compute instances, this adds complexity unless you migrate to OKE.

---

### 5. Triton Inference Server

[ developer.nvidia.com/triton-inference-server](https://developer.nvidia.com/triton-inference-server) — Open source (BSD-3)

**What it does**: High-performance inference server from NVIDIA. Supports TF, PyTorch, ONNX, TensorRT.

```
┌──────────────────┐
│  Triton Server    │
│  ─────────────── │
│  • TF backend     │
│  • PyTorch backend│
│  • ONNX backend   │
│  • Dynamic batching│
│  • Model ensemble  │
│  • GPU scheduling  │
│  • Concurrent exec│
└──────────────────┘
```

**Pros**: Fastest inference (handles GPU better than TF Serving), supports multiple frameworks, concurrent model execution.
**Cons**: No model registry, no built-in deployment pipeline. You still need to manage model storage and versioning yourself.

**Best for**: High-throughput production with GPU. Replace TF Serving for better performance.

---

## Comparison Matrix

| Framework                            | Serving | Registry | Versioning | GPU    | OCI deploy | TFRS support | Complexity |
| ------------------------------------ | ------- | -------- | ---------- | ------ | ---------- | ------------ | ---------- |
| **BentoML**                          | ✅✅    | ✅✅     | ✅✅       | ✅✅   | ✅ Docker  | ✅ Native    | Low        |
| **MLflow**                           | ✅      | ✅✅     | ✅✅       | ❌     | ✅ Docker  | ✅ Native    | Low        |
| **Ray Serve**                        | ✅✅    | ❌       | ❌         | ✅✅   | ❌ Manual  | ✅ Custom    | High       |
| **KServe**                           | ✅✅    | ❌       | ✅         | ✅✅   | ✅ OKE     | Via TF Svc   | High       |
| **Triton**                           | ✅✅✅  | ❌       | ❌         | ✅✅✅ | ✅ Docker  | ✅ Native    | Medium     |
| **TF Serving**                       | ✅✅    | ❌       | ❌         | ✅     | ✅ Docker  | ✅ Native    | Low        |
| **DIY (OCI upload + custom client)** | ✅      | ✅       | ✅         | ❌     | ✅ Native  | ✅           | High       |

---

## Recommendation for BetterBundle

**BentoML** is the best fit for your situation because:

1. **It replaces 4+ custom components**: You'd otherwise build a TF Serving client, OCI upload script, model version manager, and sync script. BentoML has all of these built-in.

2. **Your training code stays the same**: Just add `bentoml.tensorflow.save_model()` after training. No change to your two-tower model, feature transformers, or data loaders.

3. **Serving is async-native**: BentoML runners use `asyncio` internally, so no event loop blocking.

4. **OCI compatible**: `bentoml containerize` produces a Docker image you can push to OCI Container Registry and run on your existing compute instance alongside the other containers.

5. **Future-proof**: When you need GPU, BentoML handles it. When you need A/B testing, it's built-in. When you move to Kubernetes, BentoML runs there too.

### What it looks like end-to-end

```python
# 1. TRAINING (your existing trainer.py + one extra line)
import bentoml

# ... your existing training code ...
model = BetterBundleModel(query_tower, candidate_tower, product_ds)
model.compile(optimizer=tf.keras.optimizers.Adam(0.001))
model.fit(train_ds, epochs=10)

# One new line to save + version + register
bentoml.tensorflow.save_model(
    "betterbundle-tfrs", model,
    labels={"shop_id": shop_id, "env": "production"},
)
```

```bash
# 2. BUILD serving image
bentoml containerize betterbundle-tfrs:latest -t oci.io/betterbundle/tfrs:latest

# 3. DEPLOY alongside python-worker
# docker-compose.prod.yml adds:
#   - tfrs-serving: (BentoML container, auto-generated REST API)
#   - No need for shared volume, no sync script, no OCI upload code
```

```python
# 3. SERVE (in python-worker, replace inline TF call with HTTP to BentoML)
# Before:
scores = model(batch_features)  # blocks event loop

# After:
scores = await httpx.post("http://tfrs-serving:3000/predict", json=batch)
```

---

## Next Step

Do you want me to:

1. **Update the plan** to use **BentoML** instead of building TF Serving + OCI scripts from scratch?
2. **Keep raw TF Serving** for maximum control (you'll write more code)?
3. **Skip TF serving entirely** and go **pgvector-only** (simplest, no TF at all)?

The frameworks above all assume you keep TFRS. If you decide TFRS isn't worth the infra overhead, pgvector is the true zero-infrastructure option — the embeddings already exist, you just query them.
