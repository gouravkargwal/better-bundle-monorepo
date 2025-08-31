# BetterBundle ML API

FastAPI-based machine learning service for bundle analysis and cosine similarity calculations.

## Setup

### Prerequisites

1. Python 3.8+
2. pnpm (for workspace management)
3. PostgreSQL database

### Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Generate the Python Prisma client from the shared database schema:

```bash
python setup_prisma.py
```

3. Set up environment variables:

```bash
# Copy from global.env.example and configure
cp ../../global.env.example ../../local.env
```

Make sure to set the `DATABASE_URL` in your environment variables.

### Running the API

```bash
# Development
python main.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health check
- `POST /api/cosine-similarity` - Calculate cosine similarity between products
- `POST /api/bundle-analysis` - Analyze product bundles
- `POST /api/bundle-analysis/{shop_id}` - Analyze bundles using database data
- `GET /api/bundle-analysis/{shop_id}` - Get cached analysis results
- `DELETE /api/bundle-analysis/{shop_id}` - Clear cached analysis
- `POST /api/similar-products/{product_id}` - Get similar products
- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration

## Database Integration

This service uses the shared database package (`@better-bundle/database`) which contains the Prisma schema. The Python Prisma client is generated from this shared schema to ensure consistency across all services.

### Regenerating the Client

If the database schema changes, regenerate the Python client:

```bash
python setup_prisma.py
```

### Database Operations

The service connects to the database using the shared Prisma client and can:

- Fetch shop data
- Retrieve product information
- Access order data
- Save bundle analysis results
- Manage analysis jobs and notifications

## Development

The service is structured with:

- `main.py` - FastAPI application and endpoints
- `database.py` - Database configuration and connection management
- `cosine_similarity/` - ML analysis modules
- `setup_prisma.py` - Prisma client generation script

## Deployment

The service can be deployed to various platforms:

- **Railway**: Uses `railway.json` configuration
- **Cloudflare Workers**: Uses `wrangler.toml` configuration
- **Heroku**: Uses `Procfile` configuration

Make sure to set the appropriate environment variables for your deployment platform.
