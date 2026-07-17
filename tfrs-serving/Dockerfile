# BentoML TFRS Inference Service with OCI sync
# Runs startup script to sync models from OCI, then starts BentoML service

FROM python:3.11-slim

WORKDIR /app

# Install system deps for TensorFlow
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service and startup script
COPY service.py startup.py .

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run startup script, then start BentoML service
# Set BENTOML_RELOAD=1 in dev for hot-reload on code changes
CMD ["sh", "-c", "python startup.py && bentoml serve service:BetterBundleTfrs --host 0.0.0.0 --port 5000 ${BENTOML_RELOAD:+--reload}"]
