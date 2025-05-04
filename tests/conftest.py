import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.api.main import app
from fastapi.testclient import TestClient

# Import test configuration
import tests.test_config


@pytest.fixture(scope="session")
def test_db_url():
    # Use a test database URL
    return "postgresql://postgres:postgres@db:5432/webhook_test"


@pytest.fixture(scope="session")
def engine(test_db_url):
    # Create test database engine
    engine = create_engine(test_db_url.replace("/webhook_test", "/webhook_service"))
    
    # Create test database
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # Close any open transaction
        conn.execute(text("DROP DATABASE IF EXISTS webhook_test"))
        conn.execute(text("CREATE DATABASE webhook_test"))
    
    # Create engine for test database
    test_engine = create_engine(test_db_url)
    
    # Run migrations on test database
    from alembic import command
    from alembic.config import Config
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(alembic_cfg, "head")
    
    return test_engine


@pytest.fixture(scope="session")
def tables(engine):
    yield


@pytest.fixture
def db_session(engine, tables):
    # Create a new database session for a test
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    # Create a test client using the test database session
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def setup_test_env():
    # Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@db:5432/webhook_test"
    os.environ["REDIS_URL"] = "redis://:password@redis:6379/1"  # Use a different Redis DB for tests
    os.environ["CELERY_BROKER_URL"] = "redis://:password@redis:6379/1"
    os.environ["CELERY_RESULT_BACKEND"] = "redis://:password@redis:6379/1"
    
    yield
    
    # Clean up environment variables
    for key in ["ENVIRONMENT", "DATABASE_URL", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"]:
        if key in os.environ:
            del os.environ[key]