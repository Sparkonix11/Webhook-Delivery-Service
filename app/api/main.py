from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
from pathlib import Path

from app.api.endpoints import status, subscriptions, ingest, health
from app.core.config import settings
from app.core.middleware import RateLimitMiddleware
from app.services import cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Webhook Delivery Service API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Mount static files directory
app.mount("/static", StaticFiles(directory=Path(os.path.dirname(os.path.dirname(__file__))) / "static"), name="static")

# Include API routers
app.include_router(
    status.router, 
    prefix=f"{settings.API_V1_STR}/status",
    tags=["status"]
)
app.include_router(
    subscriptions.router,
    prefix=f"{settings.API_V1_STR}/subscriptions",
    tags=["subscriptions"]
)
app.include_router(
    ingest.router,
    prefix=f"{settings.API_V1_STR}/ingest",
    tags=["ingest"]
)
app.include_router(health.router, tags=["health"])

# Root redirect to UI dashboard
@app.get("/", include_in_schema=False)
def root():
    """Redirect to UI dashboard"""
    from fastapi.responses import HTMLResponse
    
    return HTMLResponse(content=open(Path(os.path.dirname(os.path.dirname(__file__))) / "static" / "index.html").read())


# Set up application startup event handlers
@app.on_event("startup")
def startup_event():
    """Initialize things at application startup"""
    # Set up cache invalidation listener
    try:
        cache.setup_cache_invalidation_listener()
        logger.info("Cache invalidation listener started")
    except Exception as e:
        logger.error(f"Failed to start cache invalidation listener: {str(e)}")