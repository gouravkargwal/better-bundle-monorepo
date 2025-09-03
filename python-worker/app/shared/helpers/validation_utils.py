"""
Validation utility functions for BetterBundle Python Worker
"""

import re
import json
import uuid
from typing import Any, Optional
from urllib.parse import urlparse


def validate_email(email: str) -> bool:
    """Validate email address format"""
    if not email:
        return False
    
    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
    return bool(re.match(email_pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not url:
        return False
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return False
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a reasonable length (7-15 digits)
    return 7 <= len(digits_only) <= 15


def validate_json(json_str: str) -> bool:
    """Validate if string is valid JSON"""
    if not json_str:
        return False
    
    try:
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def is_valid_uuid(uuid_str: str) -> bool:
    """Check if string is a valid UUID"""
    if not uuid_str:
        return False
    
    try:
        uuid.UUID(uuid_str)
        return True
    except (ValueError, AttributeError):
        return False


def validate_shopify_id(shopify_id: Any) -> bool:
    """Validate Shopify ID format"""
    if not shopify_id:
        return False
    
    # Convert to string if it's not already
    id_str = str(shopify_id)
    
    # Shopify IDs are typically numeric or alphanumeric
    # Check if it contains only alphanumeric characters
    return bool(re.match(r'^[A-Za-z0-9]+$', id_str))
