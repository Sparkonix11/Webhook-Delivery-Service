import redis
import json
import time
import hashlib
from typing import Optional, Any, Dict
from uuid import UUID
from contextlib import contextmanager
from datetime import timedelta
import logging

from app.core.config import settings

# Default timeout for Redis operations
REDIS_TIMEOUT = 2  # 2 seconds timeout

# Create Redis connection pool
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD or "redispass",  # Use default password if not set
    decode_responses=True,  # Decode responses to strings automatically
    socket_timeout=REDIS_TIMEOUT,  # Socket timeout
    socket_connect_timeout=REDIS_TIMEOUT  # Connection timeout
)

# Cache keys and default TTLs
SUBSCRIPTION_CACHE_KEY = "subscription:{}"
SUBSCRIPTION_VERSION_KEY = "subscription:version:{}"
SUBSCRIPTION_CACHE_TTL = 3600  # 1 hour
GLOBAL_VERSION_KEY = "subscription:global_version"

# Add rate limiting keys
TARGET_RATE_LIMIT_KEY = "target_rate_limit:{}"
TARGET_RATE_LIMIT_TTL = 60  # 1 minute window

# Add Redis Pub/Sub channel names
SUBSCRIPTION_UPDATE_CHANNEL = "subscription:updates"

logger = logging.getLogger(__name__)

# Redis client
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD or "redispass",  # Use default password if not set
    decode_responses=True
)

# Cache keys
SUBSCRIPTION_KEY_PREFIX = "subscription:"
CACHE_VERSION_KEY = "cache:version"
CACHE_TTL = 3600  # 1 hour in seconds

@contextmanager
def redis_timeout_handler(critical=False):
    """Context manager to handle Redis timeouts gracefully
    
    Args:
        critical: If True, will re-raise exceptions for critical operations
                 that shouldn't fail silently
    """
    try:
        yield
    except redis.exceptions.TimeoutError as e:
        logger.warning("Redis operation timed out")
        if critical:
            # Re-raise for critical operations
            logger.error("Critical Redis operation failed with timeout")
            raise
    except redis.exceptions.ConnectionError as e:
        logger.error("Redis connection error")
        if critical:
            # Re-raise for critical operations
            logger.error("Critical Redis operation failed with connection error")
            raise
    except Exception as e:
        logger.exception(f"Unexpected Redis error: {str(e)}")
        # Always re-raise unexpected errors
        raise

def cache_subscription(subscription_id: UUID, subscription_data: Dict[str, Any], ttl: int = SUBSCRIPTION_CACHE_TTL) -> bool:
    """
    Cache subscription data with versioning
    
    Args:
        subscription_id: UUID of the subscription
        subscription_data: Subscription data to cache
        ttl: Time to live in seconds
    
    Returns:
        bool: True if cached successfully
    """
    key = SUBSCRIPTION_CACHE_KEY.format(str(subscription_id))
    version_key = SUBSCRIPTION_VERSION_KEY.format(str(subscription_id))
    
    try:
        # Add current timestamp as version identifier
        current_version = int(time.time())
        subscription_data["_cache_version"] = current_version
        
        with redis_timeout_handler(critical=True):
            # Store the current version separately
            redis_client.set(version_key, str(current_version), ex=ttl*2)  # Version key lives twice as long
            
            # Update global version to signal changes to workers
            redis_client.incr(GLOBAL_VERSION_KEY)
            
            # Serialize using JSON
            serialized = json.dumps(subscription_data)
            return redis_client.set(key, serialized, ex=ttl)
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as e:
        logger.error(f"Failed to cache subscription {subscription_id}: {str(e)}")
        return False
    except TypeError:
        # Handle cases where data isn't JSON serializable
        logger.error(f"Failed to serialize subscription data for {subscription_id}")
        return False


def get_cached_subscription(subscription_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Get subscription data from cache
    
    Args:
        subscription_id: UUID of the subscription
    
    Returns:
        Optional[Dict]: Subscription data if found, None otherwise
    """
    key = SUBSCRIPTION_CACHE_KEY.format(str(subscription_id))
    version_key = SUBSCRIPTION_VERSION_KEY.format(str(subscription_id))
    
    # Use pipeline to get both data and version in one round trip
    with redis_timeout_handler():
        pipe = redis_client.pipeline()
        pipe.get(key)
        pipe.get(version_key)
        data, stored_version = pipe.execute()
        
        if not data:
            return None
        
        try:
            # Deserialize using JSON
            subscription_data = json.loads(data)
            
            # Version check to ensure data integrity
            if stored_version and "_cache_version" in subscription_data:
                if str(subscription_data["_cache_version"]) != stored_version:
                    # Version mismatch, clear cache
                    redis_client.delete(key)
                    return None
            
            return subscription_data
        except json.JSONDecodeError:
            # Clear corrupted cache
            redis_client.delete(key)
            return None
    return None


def invalidate_subscription_cache(subscription_id: UUID) -> bool:
    """
    Invalidate subscription cache by removing both the subscription data and version info
    
    This function is called whenever a subscription is updated or deleted to ensure
    that cached data is properly invalidated. It uses a Pub/Sub pattern to notify 
    workers more efficiently.
    
    Args:
        subscription_id: UUID of the subscription to invalidate
    
    Returns:
        bool: True if invalidated successfully (cache entry existed and was deleted)
    """
    key = SUBSCRIPTION_CACHE_KEY.format(str(subscription_id))
    version_key = SUBSCRIPTION_VERSION_KEY.format(str(subscription_id))
    
    try:
        with redis_timeout_handler():
            # First we delete our own copy
            pipe = redis_client.pipeline()
            pipe.delete(key)
            pipe.delete(version_key)
            results = pipe.execute()
            
            # Then notify all workers - even if our copy didn't exist
            publish_cache_invalidation(subscription_id)
            
            return results[0] > 0
    except Exception as e:
        logger.error(f"Failed to invalidate subscription cache: {str(e)}")
        return False


def get_cache_version() -> int:
    """Get the current cache version number"""
    version = redis_client.get(CACHE_VERSION_KEY)
    return int(version) if version else 0


def increment_cache_version():
    """Increment the cache version to invalidate all cached subscriptions"""
    redis_client.incr(CACHE_VERSION_KEY)


def get_subscription(subscription_id: str) -> Optional[Dict[str, Any]]:
    """Get a subscription from cache"""
    key = f"{SUBSCRIPTION_KEY_PREFIX}{subscription_id}"
    cached_data = redis_client.get(key)
    if cached_data:
        return json.loads(cached_data)
    return None


def set_subscription(subscription_id: str, data: Dict[str, Any]):
    """Cache a subscription"""
    key = f"{SUBSCRIPTION_KEY_PREFIX}{subscription_id}"
    redis_client.setex(
        key,
        timedelta(seconds=CACHE_TTL),
        json.dumps(data)
    )


def delete_subscription(subscription_id: str):
    """Delete a subscription from cache"""
    key = f"{SUBSCRIPTION_KEY_PREFIX}{subscription_id}"
    redis_client.delete(key)


def clear_subscription_cache():
    """Clear all cached subscriptions"""
    # Increment version to invalidate all cached subscriptions
    increment_cache_version()


def check_target_rate_limit(target_url: str, limit: int = 10) -> bool:
    """
    Check if a target URL has exceeded its rate limit.
    Implements a simple rolling window rate limit for webhook target URLs.
    
    Args:
        target_url: The target URL to check
        limit: Maximum number of requests allowed in the time window
        
    Returns:
        bool: True if the request can proceed, False if rate limited
    """
    # Hash the URL to create a shorter key
    url_hash = hashlib.md5(target_url.encode()).hexdigest()
    key = TARGET_RATE_LIMIT_KEY.format(url_hash)
    
    # Current timestamp
    now = int(time.time())
    
    try:
        with redis_timeout_handler():
            # Use Redis sorted set as a sliding window
            # 1. Remove older entries outside current window
            # 2. Count remaining entries
            # 3. Add current timestamp
            # 4. Set expiration
            
            pipe = redis_client.pipeline()
            
            # Remove outdated entries (older than TTL seconds)
            pipe.zremrangebyscore(key, 0, now - TARGET_RATE_LIMIT_TTL)
            
            # Count entries in current window
            pipe.zcard(key)
            
            # Add current timestamp
            pipe.zadd(key, {str(now): now})
            
            # Ensure key expiration
            pipe.expire(key, TARGET_RATE_LIMIT_TTL * 2)
            
            # Execute pipeline
            _, current_count, _, _ = pipe.execute()
            
            # Check if under limit
            return current_count < limit
    except Exception as e:
        # On error, allow the request (fail open for this feature)
        logger.warning(f"Error checking target rate limit: {str(e)}")
        return True


def setup_cache_invalidation_listener():
    """
    Set up a background thread to listen for cache invalidation events.
    Should be called once at application startup.
    """
    import threading
    import redis
    import json
    
    def cache_invalidation_listener():
        """Background thread function to listen for cache invalidation messages"""
        try:
            # Create a separate Redis connection for pub/sub
            pubsub_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or "redispass",  # Use default password if not set
                decode_responses=True
            )
            
            # Create a pubsub object
            pubsub = pubsub_client.pubsub()
            
            # Subscribe to the channel
            pubsub.subscribe(SUBSCRIPTION_UPDATE_CHANNEL)
            
            logger.info(f"Cache invalidation listener started on channel {SUBSCRIPTION_UPDATE_CHANNEL}")
            
            # Listen for messages
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        if 'action' in data and 'subscription_id' in data:
                            # Process different actions
                            if data['action'] == 'invalidate':
                                # Get the subscription ID
                                subscription_id = data['subscription_id']
                                logger.info(f"Received invalidation for subscription: {subscription_id}")
                                
                                # Delete from cache
                                key = SUBSCRIPTION_CACHE_KEY.format(subscription_id)
                                version_key = SUBSCRIPTION_VERSION_KEY.format(subscription_id)
                                redis_client.delete(key)
                                redis_client.delete(version_key)
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON in cache invalidation message: {message['data']}")
                    except Exception as e:
                        logger.exception(f"Error processing cache invalidation message: {str(e)}")
        except Exception as e:
            logger.exception(f"Cache invalidation listener error: {str(e)}")
            # Try to restart after a delay
            time.sleep(5)
            threading.Thread(target=cache_invalidation_listener, daemon=True).start()
    
    # Start the listener thread
    listener_thread = threading.Thread(target=cache_invalidation_listener, daemon=True)
    listener_thread.start()
    
    return listener_thread


def publish_cache_invalidation(subscription_id: UUID):
    """
    Publish a cache invalidation message to all workers.
    This is more efficient than having every worker check a version counter.
    
    Args:
        subscription_id: UUID of the subscription to invalidate
    """
    import json
    message = json.dumps({
        'action': 'invalidate',
        'subscription_id': str(subscription_id),
        'timestamp': time.time()
    })
    
    try:
        with redis_timeout_handler(critical=True):
            # Publish the invalidation message
            redis_client.publish(SUBSCRIPTION_UPDATE_CHANNEL, message)
            # We still update the global version for backward compatibility
            redis_client.incr(GLOBAL_VERSION_KEY)
            return True
    except Exception as e:
        logger.error(f"Failed to publish cache invalidation: {str(e)}")
        return False