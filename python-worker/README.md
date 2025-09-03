# BetterBundle Python Worker

An AI-powered Shopify analytics and machine learning platform that transforms raw Shopify data into actionable business insights and ML-powered recommendations.

## 🚀 Overview

BetterBundle Python Worker is a comprehensive backend system that provides:

- **Shopify Data Collection**: Automated collection and processing of Shopify store data
- **Machine Learning Services**: Feature engineering, ML training, and prediction pipelines
- **Business Analytics**: Comprehensive business metrics, performance analytics, and insights
- **Gorse ML Integration**: Seamless integration with Gorse recommendation engine
- **RESTful API**: Clean, documented API endpoints for all services

## 🏗️ Architecture

The system follows a clean, domain-driven architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Application                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Shopify   │  │      ML     │  │ Analytics   │        │
│  │   Domain    │  │   Domain    │  │   Domain    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Domain Structure

- **Shopify Domain**: Data collection, processing, and storage
- **ML Domain**: Feature engineering, model training, and predictions
- **Analytics Domain**: Business metrics, performance analysis, and insights

## 🛠️ Technology Stack

- **Framework**: FastAPI (Python 3.9+)
- **Async Runtime**: asyncio
- **ML Engine**: Gorse (recommendation engine)
- **Data Processing**: Custom feature engineering pipeline
- **Logging**: Structured logging with correlation IDs
- **API Documentation**: Auto-generated OpenAPI/Swagger docs

## 📁 Project Structure

```
python-worker/
├── app/
│   ├── core/                    # Core configuration and utilities
│   ├── domains/                 # Domain-specific modules
│   │   ├── shopify/            # Shopify data collection
│   │   ├── ml/                 # Machine learning services
│   │   └── analytics/          # Business analytics
│   ├── shared/                  # Shared utilities and decorators
│   └── main.py                 # Main FastAPI application
├── requirements.txt             # Python dependencies
└── README.md                   # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Gorse ML engine running
- Shopify Partner account
- Redis (for caching and job queues)

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd BetterBundle/python-worker
   ```

2. **Create virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**
   ```bash
   python -m app.main
   ```

The API will be available at `http://localhost:8000`

## 📊 API Endpoints

### Health Check

- `GET /health` - System health status

### Shopify Data

- `POST /api/shopify/collect-data` - Start data collection
- `GET /api/shopify/data-status/{shop_id}` - Get collection status

### Machine Learning

- `POST /api/ml/pipeline/run` - Run ML pipeline
- `GET /api/ml/pipeline/status/{shop_id}` - Get pipeline status

### Analytics

- `GET /api/analytics/business-metrics/{shop_id}` - Business metrics
- `GET /api/analytics/kpi-dashboard/{shop_id}` - KPI dashboard
- `GET /api/analytics/customer-insights/{shop_id}` - Customer insights
- `GET /api/analytics/product-insights/{shop_id}` - Product insights
- `GET /api/analytics/revenue-insights/{shop_id}` - Revenue insights
- `GET /api/analytics/performance/{shop_id}` - Performance analytics
- `GET /api/analytics/performance/recommendations/{shop_id}` - Optimization recommendations

## 🔧 Configuration

### Environment Variables

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Shopify Configuration
SHOPIFY_API_KEY=your_api_key
SHOPIFY_API_SECRET=your_api_secret
SHOPIFY_SCOPES=read_products,read_orders,read_customers

# Gorse ML Configuration
GORSE_API_URL=http://localhost:8088
GORSE_API_KEY=your_gorse_api_key

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/betterbundle

# Redis Configuration
REDIS_URL=redis://localhost:6379

# CORS Configuration
ALLOWED_ORIGINS=["http://localhost:3000", "https://yourdomain.com"]
```

## 🧠 Machine Learning Features

### Feature Engineering

The system automatically extracts and computes features from Shopify data:

- **Product Features**: Price, inventory, sales history, category, tags
- **Customer Features**: Purchase history, behavior patterns, demographics
- **Order Features**: Order value, frequency, payment methods, shipping
- **Shop Features**: Aggregate metrics, performance indicators
- **Cross-Entity Features**: Product-customer interactions, collection performance

### ML Models

- **Recommendation Models**: Product recommendations, customer recommendations
- **Classification Models**: Customer segmentation, product categorization
- **Regression Models**: Sales forecasting, customer lifetime value prediction

### ML Pipeline

End-to-end ML workflow including:

1. Feature Engineering
2. Model Training
3. Model Evaluation
4. Model Deployment
5. Predictions and Recommendations

## 📈 Analytics Capabilities

### Business Metrics

- Revenue analysis and forecasting
- Order metrics and trends
- Customer acquisition and retention
- Product performance and inventory
- Conversion funnel analysis
- Growth metrics and comparisons

### Performance Analytics

- Shop performance scoring
- Bottleneck identification
- Optimization recommendations
- Performance benchmarking
- Trend analysis and forecasting

### Customer Analytics

- Customer segmentation
- Lifetime value analysis
- Behavior pattern analysis
- Churn prediction
- Acquisition cost analysis

### Product Analytics

- Product performance scoring
- Sales analysis and trends
- Inventory optimization
- Category performance
- Product recommendations

### Revenue Analytics

- Revenue trend analysis
- Source/channel analysis
- Profit margin analysis
- Seasonal pattern analysis
- Revenue forecasting

## 🔄 Data Flow

```
Shopify Store → Data Collection → Feature Engineering → ML Pipeline → Analytics → Insights
     ↓              ↓                    ↓              ↓           ↓         ↓
  Raw Data    Structured Data    ML Features    Models    Metrics   Dashboard
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build the image
docker build -t betterbundle-worker .

# Run the container
docker run -p 8000:8000 --env-file .env betterbundle-worker
```

### Production Considerations

- Use production-grade database (PostgreSQL)
- Configure Redis for caching and job queues
- Set up proper logging and monitoring
- Configure CORS for production domains
- Use environment-specific configuration files
- Set up health checks and monitoring

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

### Test Structure

- Unit tests for individual services
- Integration tests for domain workflows
- API tests for endpoint functionality
- Performance tests for ML pipelines

## 📚 API Documentation

Once the application is running, you can access:

- **Interactive API Docs**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- Create an issue in the repository
- Check the API documentation
- Review the code examples
- Contact the development team

## 🔮 Roadmap

### Phase 1: Core Infrastructure ✅

- [x] Shopify data collection
- [x] Basic ML services
- [x] Analytics foundation

### Phase 2: Advanced ML ✅

- [x] Feature engineering pipeline
- [x] Gorse ML integration
- [x] ML pipeline orchestration

### Phase 3: Analytics Platform ✅

- [x] Business metrics service
- [x] Performance analytics
- [x] Customer and product insights

### Phase 4: Production Ready

- [ ] Advanced monitoring and alerting
- [ ] A/B testing framework
- [ ] Real-time analytics
- [ ] Advanced ML model management

### Phase 5: Enterprise Features

- [ ] Multi-tenant architecture
- [ ] Advanced security features
- [ ] Custom ML model support
- [ ] Advanced reporting and dashboards

---

**BetterBundle Python Worker** - Transforming Shopify data into actionable intelligence through AI and machine learning.
