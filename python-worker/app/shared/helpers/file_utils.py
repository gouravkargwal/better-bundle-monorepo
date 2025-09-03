"""
File utility functions for BetterBundle Python Worker
"""

import os
import pathlib
import re
from typing import Optional


def ensure_directory(directory_path: str) -> bool:
    """Ensure a directory exists, create if it doesn't"""
    try:
        pathlib.Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def safe_filename(filename: str, max_length: int = 255) -> str:
    """Convert filename to a safe version for filesystem"""
    if not filename:
        return "unnamed_file"
    
    # Remove or replace dangerous characters
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    safe_name = safe_name.strip('. ')
    
    # Limit length
    if len(safe_name) > max_length:
        name, ext = os.path.splitext(safe_name)
        safe_name = name[:max_length - len(ext)] + ext
    
    return safe_name or "unnamed_file"


def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    if not filename:
        return ""
    
    return pathlib.Path(filename).suffix.lower()


def get_file_size(file_path: str) -> Optional[int]:
    """Get file size in bytes"""
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError):
        return None


def is_safe_file(file_path: str, allowed_extensions: Optional[list] = None) -> bool:
    """Check if file is safe to process"""
    if not file_path:
        return False
    
    # Check if file exists
    if not os.path.isfile(file_path):
        return False
    
    # Check file extension if specified
    if allowed_extensions:
        ext = get_file_extension(file_path)
        if ext not in allowed_extensions:
            return False
    
    # Check file size (max 100MB)
    file_size = get_file_size(file_path)
    if file_size and file_size > 100 * 1024 * 1024:  # 100MB
        return False
    
    return True
