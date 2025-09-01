# BetterBundle Python Worker

A FastAPI-based worker service for data collection, processing, and event-driven ML training using Redis Streams.

## Features

- **Data Collection**: Efficient Shopify GraphQL API integration for orders, products, and customers
- **Event-Driven Architecture**: Redis Streams for async job processing and ML training coordination
- **Database Integration**: Prisma Python client for PostgreSQL operations
- **Health Monitoring**: Comprehensive health checks for database and Redis connections
- **Error Handling**: Robust retry logic and error recovery mechanisms
- **Structured Logging**: JSON-structured logging with performance metrics

## Architecture

```
Shopify App → Redis Streams → Python Worker → ML API
     ↓              ↓             ↓           ↓
  Analysis    Data Job       Process Data   Train Model
  Request     Stream         & Save         & Results
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
cp env.example .env
# Edit .env with your configuration
```

### 3. Setup Database

```bash
# Generate Prisma client
prisma generate

# Run migrations (if needed)
prisma db push
```

### 4. Run the Worker

```bash
# Development
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1
```

### 5. Start Consumer (Optional)

```bash
# Start Redis Streams consumer
curl -X POST http://localhost:8001/api/v1/data-jobs/start-consumer
```

## API Endpoints

### Health Checks

- `GET /health/` - Basic health check
- `GET /health/detailed` - Detailed health with DB and Redis status
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

### Data Jobs

- `POST /api/v1/data-jobs/queue` - Queue a data collection job
- `POST /api/v1/data-jobs/process` - Process a job directly (sync)
- `GET /api/v1/data-jobs/status/{job_id}` - Get job status
- `POST /api/v1/data-jobs/start-consumer` - Start stream consumer

### Streams

- `POST /api/v1/data-jobs/streams/ml-training` - Publish ML training event
- `POST /api/v1/data-jobs/streams/user-notification` - Publish notification

## Redis Streams

### Stream Names

- `betterbundle:data-jobs` - Data collection jobs
- `betterbundle:ml-training` - ML training requests
- `betterbundle:analysis-results` - Analysis results
- `betterbundle:user-notifications` - User notifications

### Consumer Groups

- `data-processors` - Data collection processors

## Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql://...

# Redis (Upstash)
REDIS_HOST=your-host.upstash.io
REDIS_PASSWORD=your-password
REDIS_TLS=true

# Worker Settings
WORKER_ID=python-worker-1
SHOPIFY_API_RATE_LIMIT=40
MAX_RETRIES=3
```

## Docker

```bash
# Build image
docker build -t betterbundle-python-worker .

# Run container
docker run -p 8001:8001 --env-file .env betterbundle-python-worker
```

## Development

### Project Structure

```
app/
├── main.py                 # FastAPI application
├── core/
│   ├── config.py          # Settings and configuration
│   ├── database.py        # Database connection and utilities
│   ├── redis_client.py    # Redis Streams client
│   └── logging.py         # Structured logging
├── services/
│   ├── shopify_api.py     # Shopify GraphQL client
│   ├── data_collection.py # Data collection service
│   └── data_processor.py  # Main data processor
└── api/
    └── v1/
        ├── health.py      # Health check endpoints
        └── data_jobs.py   # Data job endpoints
```

### Code Quality

```bash
# Format code
black app/

# Sort imports
isort app/

# Lint code
flake8 app/

# Run tests
pytest
```

## Monitoring

### Logs

- Structured JSON logging
- Performance metrics
- Error tracking with context
- Request/response logging

### Health Checks

- Database connection health
- Redis connection health
- Service readiness/liveness

### Metrics

- Job processing duration
- API response times
- Data collection counts
- Stream event processing

## Deployment

### Environment Setup

1. Set up PostgreSQL database
2. Configure Upstash Redis
3. Set environment variables
4. Deploy using Docker or direct Python

### Scaling

- Horizontal scaling with multiple worker instances
- Redis Streams consumer groups for load distribution
- Database connection pooling
- Rate limiting for Shopify API

## Event Flow

1. **Job Request**: Shopify app publishes data job to `data-jobs` stream
2. **Data Collection**: Worker consumes job, collects Shopify data
3. **Data Processing**: Clean and save data to PostgreSQL
4. **ML Training**: Publish ML training event to `ml-training` stream
5. **Notifications**: Publish user notifications for status updates

## Error Handling

- Exponential backoff retry logic
- Dead letter queue handling
- Database reconnection on failures
- Graceful degradation for external API failures
- Comprehensive error logging and monitoring
