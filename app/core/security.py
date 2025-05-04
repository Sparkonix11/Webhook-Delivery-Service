import hmac
import hashlib
from typing import Optional

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook signature using HMAC-SHA256
    
    Args:
        payload: Raw request body bytes
        signature: Signature header value
        secret: Secret key for the subscription
    
    Returns:
        bool: True if signature is valid
    """
    if not payload or not signature or not secret:
        return False
    
    # Calculate signature
    calculated_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures using constant-time comparison
    return hmac.compare_digest(calculated_signature, signature)


def generate_signature(payload: bytes, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for a payload
    
    Args:
        payload: Raw request body bytes
        secret: Secret key for the subscription
    
    Returns:
        str: Generated signature
    """
    return hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()