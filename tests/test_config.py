from app.core.config import settings

# Database settings
settings.POSTGRES_SERVER = "db"
settings.POSTGRES_USER = "postgres"
settings.POSTGRES_PASSWORD = "postgres"
settings.POSTGRES_DB = "webhook_service"

# Redis settings
settings.REDIS_HOST = "redis"
settings.REDIS_PORT = 6379
settings.REDIS_DB = 0  # Use the same Redis DB as the main application
settings.REDIS_PASSWORD = "password"  # Match the password in .env file

# Disable rate limiting for tests
settings.RATE_LIMIT_ENABLED = False