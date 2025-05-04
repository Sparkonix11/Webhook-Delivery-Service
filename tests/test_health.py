import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.redis import redis_client
from app.api.main import app

client = TestClient(app)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    yield Session(engine)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_redis():
    with patch("app.redis.redis_client") as mock:
        yield mock


@pytest.fixture
def mock_celery():
    with patch("app.workers.celery_app") as mock:
        yield mock


def test_health_check_success(db: Session, mock_redis, mock_celery):
    # Mock Redis connection
    mock_redis.ping.return_value = True
    
    # Mock Celery worker status
    mock_celery.control.inspect.return_value.ping.return_value = {"celery@worker": "pong"}
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "healthy"
    assert data["redis"] == "healthy"
    assert data["celery"] == "healthy"


def test_health_check_database_failure(db: Session, mock_redis, mock_celery):
    # Mock Redis connection
    mock_redis.ping.return_value = True
    
    # Mock Celery worker status
    mock_celery.control.inspect.return_value.ping.return_value = {"celery@worker": "pong"}
    
    # Force database connection to fail
    with patch("app.db.session.SessionLocal") as mock_db:
        mock_db.side_effect = Exception("Database connection failed")
        
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "unhealthy"
        assert "Database connection failed" in data["error"]


def test_health_check_redis_failure(db: Session, mock_redis, mock_celery):
    # Mock Redis connection failure
    mock_redis.ping.side_effect = Exception("Redis connection failed")
    
    # Mock Celery worker status
    mock_celery.control.inspect.return_value.ping.return_value = {"celery@worker": "pong"}
    
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["redis"] == "unhealthy"
    assert "Redis connection failed" in data["error"]


def test_health_check_celery_failure(db: Session, mock_redis, mock_celery):
    # Mock Redis connection
    mock_redis.ping.return_value = True
    
    # Mock Celery worker failure
    mock_celery.control.inspect.return_value.ping.side_effect = Exception("Celery worker not responding")
    
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["celery"] == "unhealthy"
    assert "Celery worker not responding" in data["error"] 