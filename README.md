# Webhook Delivery Service

A robust webhook delivery service capable of ingesting, queuing, and delivering webhook payloads to subscribed URLs with retry capabilities and comprehensive logging.

## Live Demo

Access the live deployed application at: [https://segwiseintern.site/](https://segwiseintern.site/)

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

## Architecture Choices

### Framework: FastAPI
FastAPI was chosen for its high performance, automatic documentation generation, built-in validation, and async support. The asynchronous nature of FastAPI makes it ideal for a webhook service that needs to handle multiple concurrent requests efficiently.

### Database: PostgreSQL
PostgreSQL was selected for its reliability, ACID compliance, and excellent support for complex queries. The structured nature of webhook subscription and delivery data fits well with PostgreSQL's relational model. The database stores subscription details, delivery attempts, and logs.

### Caching & Message Broker: Redis
Redis serves dual purposes:
1. As a caching layer to reduce database load for frequently accessed data
2. As a message broker for the task queue system (Celery)

### Task Queue System: Celery
Celery manages asynchronous webhook delivery tasks, allowing the API to respond quickly while delivery happens in the background. This architecture supports high throughput and prevents delivery issues from affecting API responsiveness.

### Retry Strategy
The service implements an exponential backoff strategy for failed webhook deliveries:
- Initial delay: 30 seconds
- Maximum attempts: 8
- Backoff factor: 2
- Maximum delay: 1 hour

This approach reduces load on receiving systems during outages while ensuring timely delivery once the recipient is available again.

## Database Schema & Indexing

### Core Tables

#### subscriptions
- `id`: UUID primary key
- `target_url`: VARCHAR(255), indexed for efficient lookups
- `secret`: TEXT (nullable), stores the HMAC secret
- `event_types`: JSONB (nullable), indexed using GIN for efficient JSON array lookups
- `created_at`: TIMESTAMP WITH TIME ZONE
- `updated_at`: TIMESTAMP WITH TIME ZONE

#### delivery_tasks
- `id`: UUID primary key
- `subscription_id`: UUID, foreign key to subscriptions.id, indexed
- `event_type`: VARCHAR(100), indexed for filtering by event type
- `payload`: JSONB, stores the webhook payload
- `status`: VARCHAR(20), indexed for quick status filtering
- `attempts`: INTEGER, tracks number of delivery attempts
- `last_attempt_at`: TIMESTAMP WITH TIME ZONE
- `next_attempt_at`: TIMESTAMP WITH TIME ZONE, indexed for worker queue processing
- `created_at`: TIMESTAMP WITH TIME ZONE, indexed with TTL for log retention policy

#### delivery_logs
- `id`: UUID primary key
- `delivery_task_id`: UUID, foreign key to delivery_tasks.id, indexed
- `attempt_number`: INTEGER
- `status`: VARCHAR(20), indexed for filtering successful/failed deliveries
- `status_code`: INTEGER (nullable), HTTP status code
- `error_details`: TEXT (nullable)
- `created_at`: TIMESTAMP WITH TIME ZONE, indexed with TTL for log retention policy

### Indexing Strategy
- B-Tree indexes on foreign keys and frequently filtered columns
- GIN index on JSON fields to allow efficient filtering by event types
- Partial indexes on status fields to optimize common queries
- Time-based indexes to support the log retention policy

## Local Setup with Docker

### Prerequisites
- Docker Engine (20.10+)
- Docker Compose (2.0+)
- Git

### Step-by-Step Instructions

1. Clone the repository:
```bash
git clone https://github.com/Sparkonix11/segwise-assignment.git
cd segwise-assignment
```

2. Create a `.env` file in the project root (or use the provided example):
```bash
cp .env.example .env
```

3. Build and start the services:
```bash
docker-compose up -d
```

4. Verify all services are running:
```bash
docker-compose ps
```

5. Run database migrations:
```bash
docker-compose exec api alembic upgrade head
```

6. Access the application:
   - Web UI: http://localhost:8000

7. To stop the services:
```bash
docker-compose down
```

## API Usage Examples

### Subscription Management

#### Create a subscription
```bash
curl -X POST http://localhost:8000/api/v1/subscriptions/ \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://webhook.site/your-webhook-id",
    "secret": "your-secret-key",
    "event_types": ["order.created", "user.registered"]
  }'
```

#### List all subscriptions
```bash
curl -X GET http://localhost:8000/api/v1/subscriptions/
```

#### Get a specific subscription
```bash
curl -X GET http://localhost:8000/api/v1/subscriptions/123e4567-e89b-12d3-a456-426614174000
```

#### Update a subscription
```bash
curl -X PUT http://localhost:8000/api/v1/subscriptions/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://new-webhook-endpoint.com/hook",
    "event_types": ["order.created", "order.updated", "order.canceled"]
  }'
```

#### Delete a subscription
```bash
curl -X DELETE http://localhost:8000/api/v1/subscriptions/123e4567-e89b-12d3-a456-426614174000
```

### Webhook Ingestion and Delivery

#### Send a webhook event
```bash
curl -X POST http://localhost:8000/api/v1/ingest/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "data": {
      "order_id": "ORD-12345",
      "customer": "John Doe",
      "total": 99.99,
      "items": [
        {"product_id": "PROD-1", "quantity": 2, "price": 49.99}
      ]
    }
  }'
```

#### Check delivery status
```bash
curl -X GET http://localhost:8000/api/v1/ingest/delivery/456e7890-e89b-12d3-a456-426614174000
```

#### Get recent deliveries for a subscription
```bash
curl -X GET http://localhost:8000/api/v1/subscriptions/123e4567-e89b-12d3-a456-426614174000/deliveries
```

### Health and Status

#### Check service health
```bash
curl -X GET http://localhost:8000/api/v1/health
```

#### Get system status
```bash
curl -X GET http://localhost:8000/api/v1/status
```

## Cost Estimation (Free Tier)

Assuming continuous operation (24/7) and moderate traffic (5,000 webhooks/day with avg. 1.2 delivery attempts per webhook):

### Google Cloud Platform Free Tier
- **Compute Engine (e2-micro)**: 
  - 1 for API: ₹0.00 (1 free e2-micro instance per month)
  - 1 for workers: ~₹665/month (additional instance not covered by free tier)
- **Cloud SQL (db-f1-micro)**: ₹0.00 (uses Google Cloud Free Tier for the first 3 months, then ~₹750/month)
- **Memorystore (Redis) Basic Tier**: ~₹1,080/month (smallest instance, not covered by free tier)
- **Cloud Storage**: ~₹0.00 (under 5GB stays within free tier limits)
- **Data Transfer**: ~₹0.00 (under 1GB/day stays within free tier limits)

### Total Monthly Cost:
- First 3 months: ~₹1,745/month
- After 3 months: ~₹2,495/month

### Additional Considerations
- App Engine's standard environment could be an alternative with a more generous free tier for the API component
- Webhook traffic exceeding 5,000/day would increase Compute Engine and Memorystore costs
- Cloud Functions could handle webhook delivery for very low volumes at a potentially lower cost
- For production, additional instances for high availability would be recommended
- Monitoring via Cloud Monitoring includes a free tier but may add costs for custom metrics
- Cloud Armor (for security) would add ~₹415/month if required

*Note: Exchange rate used is approximately ₹83 = $1 (as of May 2025). Actual costs may vary based on exchange rate fluctuations and GCP pricing changes.*

## Credits

### Libraries & Frameworks
- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit and ORM
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Celery](https://docs.celeryproject.org/) - Distributed task queue
- [Redis](https://redis.io/) - In-memory data store
- [PostgreSQL](https://www.postgresql.org/) - Relational database
- [Alembic](https://alembic.sqlalchemy.org/) - Database migrations
- [pytest](https://docs.pytest.org/) - Testing framework
- [Bootstrap](https://getbootstrap.com/) - Frontend framework

### Tools
- [Docker](https://www.docker.com/) - Containerization
