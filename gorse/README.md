# Gorse Recommendation Engine

This is a deployment of Gorse, an open-source recommendation system, configured for Render.

## Deployment on Render

### Prerequisites

1. **Render PostgreSQL Database**

   - Create a new PostgreSQL database on Render
   - Note down the `DATABASE_URL` from the database settings

2. **Upstash Redis Database**
   - Create a new Redis database on Upstash
   - Note down the `REDIS_URL` from the database settings

### Deployment Steps

1. **Connect your repository to Render**

   - Push this code to your GitHub repository
   - Connect the repository to Render

2. **Set Environment Variables**
   In your Render service settings, add these environment variables:

   - `GORSE_DATA_STORE`: Your Render PostgreSQL connection string
   - `GORSE_CACHE_STORE`: Your Upstash Redis connection string

3. **Deploy**
   - Render will automatically build and deploy the service
   - The service will be available at your Render URL

### Environment Variables

- `GORSE_DATA_STORE`: PostgreSQL connection string (from Render)
- `GORSE_CACHE_STORE`: Redis connection string (from Upstash)

### API Endpoints

Once deployed, you can access:

- Dashboard: `https://your-app.onrender.com`
- API: `https://your-app.onrender.com/api/`

### Example Usage

```bash
# Insert feedback
curl -X POST https://your-app.onrender.com/api/feedback \
  -H 'Content-Type: application/json' \
  -d '[
    {"FeedbackType": "star", "UserId": "user1", "ItemId": "item1", "Timestamp": "2024-01-01"}
  ]'

# Get recommendations
curl https://your-app.onrender.com/api/recommend/user1?n=10
```
