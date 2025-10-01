# Billing Scheduler Service

A comprehensive billing scheduler service that calculates bills for all active shops and can be triggered by GitHub Actions, cron jobs, or manual API calls.

## Features

- **Automated Billing**: Calculate monthly bills for all active shops
- **GitHub Actions Integration**: Trigger billing via GitHub Actions workflows
- **API Endpoints**: RESTful API for manual billing triggers
- **CLI Interface**: Command-line interface for testing and debugging
- **Dry Run Mode**: Calculate bills without creating invoices
- **Shop-specific Processing**: Process billing for specific shops
- **Comprehensive Logging**: Detailed logging and error tracking
- **Background Processing**: Asynchronous processing for large-scale operations

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub        │    │   API            │    │   CLI           │
│   Actions       │───▶│   Endpoints      │───▶│   Interface     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Billing         │
                       │  Scheduler       │
                       │  Service         │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Billing         │
                       │  Calculator      │
                       │  & Repository    │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Database        │
                       │  (SQLAlchemy)    │
                       └──────────────────┘
```

## Components

### 1. BillingSchedulerService

Main service class that orchestrates the billing process.

**Key Methods:**

- `process_monthly_billing()`: Process billing for all or specific shops
- `process_shop_billing()`: Process billing for a single shop
- `get_billing_status()`: Get current billing status and statistics

### 2. API Endpoints

RESTful API endpoints for triggering and monitoring billing.

**Endpoints:**

- `POST /api/billing-scheduler/process-monthly-billing`: Process monthly billing
- `POST /api/billing-scheduler/process-shop-billing/{shop_id}`: Process specific shop
- `POST /api/billing-scheduler/github-webhook`: GitHub webhook endpoint
- `GET /api/billing-scheduler/status`: Get billing status
- `GET /api/billing-scheduler/health`: Health check

### 3. GitHub Actions Workflow

Automated workflow for scheduled billing processing.

**Triggers:**

- Manual workflow dispatch
- Monthly schedule (1st of month at 2 AM UTC)
- Repository dispatch events
- Push to main branch (for testing)

### 4. CLI Interface

Command-line interface for testing and debugging.

**Commands:**

- `python billing_scheduler_cli.py process`: Process billing
- `python billing_scheduler_cli.py status`: Get status
- `python billing_scheduler_cli.py test {shop_id}`: Test specific shop

## Usage

### 1. GitHub Actions Trigger

The billing scheduler can be triggered automatically via GitHub Actions:

```yaml
# Manual trigger
workflow_dispatch:
  inputs:
    dry_run: true
    shop_ids: "shop1,shop2,shop3"

# Scheduled trigger (monthly)
schedule:
  - cron: "0 2 1 * *"
```

### 2. API Trigger

```bash
# Process all shops (dry run)
curl -X POST "http://localhost:8000/api/billing-scheduler/process-monthly-billing" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Process specific shops
curl -X POST "http://localhost:8000/api/billing-scheduler/process-monthly-billing" \
  -H "Content-Type: application/json" \
  -d '{"shop_ids": ["shop1", "shop2"], "dry_run": false}'

# Get status
curl -X GET "http://localhost:8000/api/billing-scheduler/status"
```

### 3. CLI Usage

```bash
# Process billing for all shops (dry run)
python app/scripts/billing_scheduler_cli.py process --dry-run

# Process billing for specific shops
python app/scripts/billing_scheduler_cli.py process --shop-ids shop1 shop2

# Process billing for previous month
python app/scripts/billing_scheduler_cli.py process --previous-month

# Test billing for a specific shop
python app/scripts/billing_scheduler_cli.py test shop1 --dry-run

# Get billing status
python app/scripts/billing_scheduler_cli.py status
```

### 4. Programmatic Usage

```python
from app.services.billing_scheduler_service import BillingSchedulerService

# Initialize service
scheduler = BillingSchedulerService()
await scheduler.initialize()

# Process billing for all shops
result = await scheduler.process_monthly_billing(
    shop_ids=None,  # All active shops
    period=None,   # Previous month
    dry_run=True   # Calculate but don't create invoices
)

# Process billing for specific shop
result = await scheduler.process_shop_billing(
    shop_id="shop123",
    period=None,
    dry_run=False
)
```

## Configuration

The billing scheduler can be configured via environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/db

# Redis
REDIS_URL=redis://localhost:6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# API
API_BASE_URL=http://localhost:8000

# GitHub Integration
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_API_TOKEN=your_api_token

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
BILLING_NOTIFICATION_WEBHOOK_URL=https://your-webhook-url.com
```

## Billing Process Flow

1. **Trigger**: Billing is triggered by GitHub Actions, API call, or CLI
2. **Shop Selection**: Get list of active shops with billing plans
3. **Period Calculation**: Determine billing period (default: previous month)
4. **Shop Processing**: For each shop:
   - Load shop data and billing plan
   - Calculate attribution metrics
   - Run fraud detection
   - Calculate billing fee
   - Create invoice (if not dry run)
5. **Results**: Return processing results with success/failure counts

## Error Handling

- **Retry Logic**: Failed shops are retried up to 3 times
- **Error Logging**: All errors are logged with detailed context
- **Graceful Degradation**: Partial failures don't stop the entire process
- **DLQ Support**: Failed messages can be sent to Dead Letter Queue

## Monitoring

- **Health Checks**: `/api/billing-scheduler/health` endpoint
- **Status Monitoring**: `/api/billing-scheduler/status` endpoint
- **Metrics**: Built-in metrics collection
- **Logging**: Structured logging with correlation IDs

## Testing

### Unit Tests

```bash
pytest app/tests/test_billing_scheduler_service.py
```

### Integration Tests

```bash
pytest app/tests/test_billing_scheduler_integration.py
```

### Manual Testing

```bash
# Test with dry run
python app/scripts/billing_scheduler_cli.py process --dry-run

# Test specific shop
python app/scripts/billing_scheduler_cli.py test shop123 --dry-run
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app/scripts/billing_scheduler_cli.py", "process"]
```

### Kubernetes

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: billing-scheduler
spec:
  schedule: "0 2 1 * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: billing-scheduler
              image: your-image:latest
              command:
                ["python", "app/scripts/billing_scheduler_cli.py", "process"]
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**

   - Check DATABASE_URL configuration
   - Verify database connectivity
   - Check connection pool settings

2. **Shop Processing Failures**

   - Check shop data integrity
   - Verify billing plan configuration
   - Review attribution data availability

3. **GitHub Actions Failures**
   - Verify webhook secret configuration
   - Check GitHub API token permissions
   - Review workflow logs

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python app/scripts/billing_scheduler_cli.py process --dry-run
```

### Log Analysis

```bash
# View recent billing logs
tail -f logs/billing_scheduler.log

# Search for errors
grep "ERROR" logs/billing_scheduler.log

# Monitor specific shop
grep "shop123" logs/billing_scheduler.log
```

## Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Test with dry run mode first
5. Verify GitHub Actions integration

## License

This project is licensed under the MIT License.
