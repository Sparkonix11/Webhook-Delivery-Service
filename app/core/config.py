from typing import Optional, Dict, Any, List, Union
from pydantic import validator, AnyHttpUrl, PostgresDsn
from pydantic_settings import BaseSettings
import secrets
from datetime import timedelta


class Settings(BaseSettings):
    PROJECT_NAME: str = "Webhook Delivery Service"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    DB_CONNECTION_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_MAX_RETRIES: int = 3  # Maximum number of database operation retries
    DB_MAX_RETRY_DELAY: int = 30  # Maximum delay between retries in seconds

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        
        # Build the connection string directly to avoid PostgresDsn formatting issues
        return f"postgresql://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB') or ''}"
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # Webhook Settings
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_MAX_RETRIES: int = 5
    WEBHOOK_RETRY_DELAYS: List[int] = [10, 30, 60, 300, 900]  # in seconds (10s, 30s, 1m, 5m, 15m)
    MAX_WEBHOOK_PAYLOAD_SIZE: int = 1024 * 1024  # 1MB
    VERIFY_SSL_CERTIFICATES: bool = True  # Enable SSL cert verification
    TARGET_URL_RATE_LIMIT: int = 10  # Max webhooks per minute to a single target URL
    
    # Log Retention
    LOG_RETENTION_HOURS: int = 72  # 3 days
    FAILED_TASK_RETENTION_DAYS: int = 7  # 7 days
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STRATEGY: str = "fixed-window"  # options: fixed-window, sliding-window
    RATE_LIMIT_DEFAULT_LIMIT: int = 100  # requests per window
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # seconds (1 minute window)
    RATE_LIMIT_REDIS_PREFIX: str = "ratelimit:"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @validator("WEBHOOK_RETRY_DELAYS", pre=True)
    def parse_webhook_retry_delays(cls, v: Union[str, List[int]]) -> List[int]:
        if isinstance(v, str):
            try:
                # Try to parse as JSON first
                import json
                return json.loads(v)
            except json.JSONDecodeError:
                # If not valid JSON, try to parse as comma-separated string
                return [int(x.strip()) for x in v.split(",")]
        return v

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"  # Allow extra fields/environment variables


settings = Settings()