"""
String utility functions for BetterBundle Python Worker
"""

import re
import uuid
import unicodedata
from typing import List, Optional


def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    """Sanitize a string by removing dangerous characters and limiting length"""
    if not text:
        return ""
    
    # Remove control characters and normalize
    sanitized = "".join(char for char in text if unicodedata.category(char)[0] != 'C')
    sanitized = unicodedata.normalize('NFKC', sanitized)
    
    # Remove HTML tags
    sanitized = re.sub(r'<[^>]+>', '', sanitized)
    
    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()


def generate_id(prefix: str = "", length: int = 8) -> str:
    """Generate a unique ID with optional prefix"""
    if prefix:
        return f"{prefix}_{uuid.uuid4().hex[:length]}"
    return uuid.uuid4().hex[:length]


def slugify(text: str, separator: str = "-") -> str:
    """Convert text to URL-friendly slug"""
    if not text:
        return ""
    
    # Convert to lowercase and normalize
    text = unicodedata.normalize('NFKD', text.lower())
    
    # Remove non-alphanumeric characters
    text = re.sub(r'[^\w\s-]', '', text)
    
    # Replace spaces and underscores with separator
    text = re.sub(r'[-\s]+', separator, text)
    
    # Remove leading/trailing separators
    text = text.strip(separator)
    
    return text


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text"""
    if not text:
        return []
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    
    return list(set(emails))  # Remove duplicates


def extract_urls(text: str) -> List[str]:
    """Extract URLs from text"""
    if not text:
        return []
    
    url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
    urls = re.findall(url_pattern, text)
    
    return list(set(urls))  # Remove duplicates
