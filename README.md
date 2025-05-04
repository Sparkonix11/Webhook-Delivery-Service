# Webhook Delivery Service

A robust webhook delivery service capable of ingesting, queuing, and delivering webhook payloads to subscribed URLs with retry capabilities and comprehensive logging.

## Features

- Subscription management (CRUD operations)
- Asynchronous webhook delivery
- Automatic retry mechanism with exponential backoff
- Comprehensive delivery logging
- Log retention policy (72 hours)
- HMAC signature verification
- Event type filtering
- Health monitoring
- Containerized deployment

## Technology Stack

- Python 3.9
- FastAPI
- PostgreSQL
- Redis
- Celery
- Docker & Docker Compose

## Prerequisites

- Docker
- Docker Compose
- Make (optional)

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/webhook-delivery-service.git
cd webhook-delivery-service
```

2. Start the services:
```bash
docker-compose up -d
```

3. Access the API documentation:
```
http://localhost:8000/docs
```

## API Endpoints

### Health Check
- `GET /health` - Check service health

### Subscriptions
- `POST /subscriptions` - Create a new subscription
- `GET /subscriptions` - List all subscriptions
- `GET /subscriptions/{id}` - Get a specific subscription
- `PUT /subscriptions/{id}` - Update a subscription
- `DELETE /subscriptions/{id}` - Delete a subscription

### Webhook Ingestion
- `POST /ingest/{subscription_id}` - Ingest a webhook payload

### Delivery Status
- `GET /delivery/{delivery_task_id}` - Get delivery status
- `GET /subscriptions/{id}/deliveries` - List recent deliveries

## Configuration

The service can be configured using environment variables:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/webhook_service

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["*"]

# Logging
LOG_LEVEL=INFO
LOG_RETENTION_HOURS=72
```

## Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run tests:
```bash
pytest
```

## Deployment

The service is designed to be deployed using Docker Compose. Resource limits are configured to work within free tier constraints:

- API: 512MB RAM, 1 CPU
- Worker: 512MB RAM, 1 CPU
- Beat: 256MB RAM, 0.5 CPU
- Database: 1GB RAM, 1 CPU
- Redis: 256MB RAM, 0.5 CPU

## Monitoring

The service includes health checks for all components:
- API health endpoint
- Database connection monitoring
- Redis connection monitoring
- Celery worker monitoring

## Security

- HMAC-SHA256 signature verification for webhook payloads
- Secure storage of subscription secrets
- CORS configuration
- Rate limiting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License