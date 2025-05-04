from typing import Callable, Dict, Optional
import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import hashlib
import logging

from app.services.cache import redis_client
from app.core.config import settings


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI
    
    Implements a fixed-window or sliding-window rate limiting strategy
    using Redis as the backend store. Properly supports distributed deployments
    by using atomic Redis operations.
    """
    
    def __init__(
        self, 
        app: FastAPI,
        limit: int = None,
        window: int = None,
        strategy: str = None
    ):
        super().__init__(app)
        self.limit = limit or settings.RATE_LIMIT_DEFAULT_LIMIT
        self.window = window or settings.RATE_LIMIT_DEFAULT_WINDOW
        self.strategy = strategy or settings.RATE_LIMIT_STRATEGY
        self.prefix = settings.RATE_LIMIT_REDIS_PREFIX
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Skip rate limiting for certain paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)
        
        # Get client identifier (IP address, or X-Forwarded-For if available)
        client_ip = request.headers.get("X-Forwarded-For", request.client.host)
        if client_ip and "," in client_ip:
            # In case of multiple IP addresses, use the first one (typically the client's real IP)
            client_ip = client_ip.split(",")[0].strip()
            
        # Add request ID for better tracing across distributed systems
        request_id = request.headers.get("X-Request-ID", hashlib.md5(str(time.time()).encode()).hexdigest()[:8])
        
        # Add more entropy to avoid collisions in distributed environment
        instance_id = getattr(settings, "INSTANCE_ID", "default")
        
        # Create a key that includes the route path to have per-endpoint limits
        route_key = hashlib.md5(request.url.path.encode()).hexdigest()[:8]
        rate_limit_key = f"{self.prefix}{client_ip}:{route_key}"
        
        # Check if client has exceeded the rate limit
        current_time = int(time.time())
        window_start = current_time - (current_time % self.window) if self.strategy == 'fixed-window' else current_time - self.window
        
        # Use Redis pipeline for atomic operations
        try:
            pipe = redis_client.pipeline()
            
            if self.strategy == 'fixed-window':
                # Simple fixed window strategy - improved for distributed systems
                # Use Redis hash to store counts across distributed instances
                # This is more efficient than simple incr because we can check/increment atomically
                
                # Hash field is the window start timestamp for fixed windows
                window_key = f"{int(window_start)}"
                
                # Script to atomically check and increment 
                # This ensures we don't have race conditions between check and increment
                check_and_incr_script = """
                local count = redis.call('HGET', KEYS[1], ARGV[1]) 
                count = count or 0
                if tonumber(count) >= tonumber(ARGV[2]) then
                    return {0, count} -- limit exceeded
                end
                count = redis.call('HINCRBY', KEYS[1], ARGV[1], 1)
                redis.call('EXPIRE', KEYS[1], ARGV[3])
                return {1, count} -- allowed
                """
                
                result = redis_client.eval(
                    check_and_incr_script, 
                    1,  # num keys
                    rate_limit_key,  # KEYS[1]
                    window_key,  # ARGV[1] 
                    self.limit,  # ARGV[2]
                    self.window * 2  # ARGV[3] - expire after 2x window
                )
                
                allowed = bool(result[0])
                current_count = int(result[1])
                
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded",
                            "limit": self.limit,
                            "window": f"{self.window} seconds",
                            "retry_after": self.window - (current_time % self.window),
                            "request_id": request_id
                        }
                    )
            else:
                # Sliding window strategy using Redis sorted set
                # Better distributed algorithm that avoids race conditions
                
                # Use Lua script for atomic operations
                sliding_window_script = """
                -- Remove old requests outside the current window
                redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
                -- Count requests in the current window
                local count = redis.call('ZCARD', KEYS[1])
                -- Check if under limit
                if tonumber(count) >= tonumber(ARGV[2]) then
                    -- Get the oldest entry's score for retry-after
                    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
                    if oldest and #oldest > 0 then
                        return {0, count, oldest[2]} -- exceeded with oldest timestamp
                    else
                        return {0, count, 0} -- exceeded but no entries
                    end
                end
                -- Add current request with timestamp and instance ID as value
                redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
                -- Set expiration
                redis.call('EXPIRE', KEYS[1], ARGV[5])
                return {1, count + 1, 0} -- allowed
                """
                
                result = redis_client.eval(
                    sliding_window_script,
                    1,  # num keys
                    rate_limit_key,  # KEYS[1]
                    window_start,  # ARGV[1] - window start time
                    self.limit,  # ARGV[2] - rate limit
                    current_time,  # ARGV[3] - current timestamp for score
                    f"{instance_id}:{request_id}",  # ARGV[4] - unique request identifier
                    self.window * 2  # ARGV[5] - expire after 2x window
                )
                
                allowed = bool(result[0])
                current_count = int(result[1])
                oldest_timestamp = result[2]
                
                if not allowed:
                    # Calculate retry-after based on when the oldest entry expires from window
                    retry_after = 1  # Default fallback
                    if oldest_timestamp:
                        # When will the oldest entry move out of the window?
                        retry_after = max(1, int(oldest_timestamp) + self.window - current_time)
                    
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded",
                            "limit": self.limit,
                            "window": f"{self.window} seconds",
                            "retry_after": retry_after,
                            "request_id": request_id
                        }
                    )

            # Process the request normally if under limit
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers["X-Rate-Limit-Limit"] = str(self.limit)
            response.headers["X-Rate-Limit-Remaining"] = str(max(0, self.limit - current_count))
            response.headers["X-Rate-Limit-Reset"] = str(self.window - (current_time % self.window) if self.strategy == 'fixed-window' else self.window)
            response.headers["X-Request-ID"] = request_id
            
            return response
        except Exception as e:
            # Log the error but allow the request to proceed (fail open)
            # This prevents rate limiting errors from blocking legitimate traffic
            logger.error(f"Rate limiting error: {str(e)}")
            response = await call_next(request)
            response.headers["X-Rate-Limit-Error"] = "1"
            return response