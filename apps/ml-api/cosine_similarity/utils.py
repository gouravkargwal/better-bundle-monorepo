"""
Utility functions for cosine similarity analysis
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for better similarity matching
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Convert to lowercase and remove extra whitespace
    normalized = text.lower().strip()
    
    # Remove special characters but keep spaces
    import re
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized


def calculate_price_similarity(price1: float, price2: float) -> float:
    """
    Calculate similarity between two prices
    
    Args:
        price1: First price
        price2: Second price
        
    Returns:
        Similarity score between 0 and 1
    """
    if price1 == 0 and price2 == 0:
        return 1.0
    
    if price1 == 0 or price2 == 0:
        return 0.0
    
    # Use log scale for price comparison
    log_price1 = np.log(price1)
    log_price2 = np.log(price2)
    
    # Calculate similarity based on difference
    diff = abs(log_price1 - log_price2)
    max_diff = 5  # Maximum expected log difference
    
    similarity = max(0, 1 - (diff / max_diff))
    return similarity


def extract_category_features(categories: List[str]) -> Dict[str, float]:
    """
    Extract features from product categories
    
    Args:
        categories: List of category strings
        
    Returns:
        Dictionary of category features
    """
    features = {}
    
    for category in categories:
        if not category:
            continue
            
        # Normalize category
        normalized = normalize_text(category)
        
        # Split into words
        words = normalized.split()
        
        for word in words:
            if len(word) > 2:  # Skip very short words
                features[word] = features.get(word, 0) + 1
    
    return features


def calculate_category_similarity(cat1: str, cat2: str) -> float:
    """
    Calculate similarity between two categories
    
    Args:
        cat1: First category
        cat2: Second category
        
    Returns:
        Similarity score between 0 and 1
    """
    if not cat1 or not cat2:
        return 0.0
    
    # Normalize categories
    norm_cat1 = normalize_text(cat1)
    norm_cat2 = normalize_text(cat2)
    
    # Exact match
    if norm_cat1 == norm_cat2:
        return 1.0
    
    # Extract features
    features1 = extract_category_features([norm_cat1])
    features2 = extract_category_features([norm_cat2])
    
    # Calculate Jaccard similarity
    words1 = set(features1.keys())
    words2 = set(features2.keys())
    
    if not words1 and not words2:
        return 0.0
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0


def calculate_tag_similarity(tags1: List[str], tags2: List[str]) -> float:
    """
    Calculate similarity between two sets of tags
    
    Args:
        tags1: First set of tags
        tags2: Second set of tags
        
    Returns:
        Similarity score between 0 and 1
    """
    if not tags1 and not tags2:
        return 1.0
    
    if not tags1 or not tags2:
        return 0.0
    
    # Normalize tags
    norm_tags1 = [normalize_text(tag) for tag in tags1 if tag]
    norm_tags2 = [normalize_text(tag) for tag in tags2 if tag]
    
    # Convert to sets
    set1 = set(norm_tags1)
    set2 = set(norm_tags2)
    
    # Calculate Jaccard similarity
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0


def create_feature_vector(
    title: str,
    category: str,
    price: float,
    tags: List[str],
    description: str = "",
    has_image: bool = False
) -> Dict[str, float]:
    """
    Create a feature vector for a product
    
    Args:
        title: Product title
        category: Product category
        price: Product price
        tags: Product tags
        description: Product description
        has_image: Whether product has image
        
    Returns:
        Dictionary of features
    """
    features = {}
    
    # Text features (normalized)
    features['title_normalized'] = len(normalize_text(title))
    features['category_normalized'] = len(normalize_text(category))
    features['description_normalized'] = len(normalize_text(description))
    
    # Price features
    features['price_log'] = np.log1p(price) if price > 0 else 0
    features['price_bucket'] = np.floor(np.log10(price)) if price > 0 else 0
    
    # Tag features
    features['tag_count'] = len(tags) if tags else 0
    features['avg_tag_length'] = np.mean([len(tag) for tag in tags]) if tags else 0
    
    # Image feature
    features['has_image'] = 1.0 if has_image else 0.0
    
    # Combined text length
    all_text = f"{title} {category} {description} {' '.join(tags) if tags else ''}"
    features['total_text_length'] = len(normalize_text(all_text))
    
    return features


def calculate_feature_similarity(features1: Dict[str, float], features2: Dict[str, float]) -> float:
    """
    Calculate similarity between two feature vectors
    
    Args:
        features1: First feature vector
        features2: Second feature vector
        
    Returns:
        Similarity score between 0 and 1
    """
    # Get all feature keys
    all_keys = set(features1.keys()).union(set(features2.keys()))
    
    if not all_keys:
        return 0.0
    
    # Calculate cosine similarity
    dot_product = 0
    norm1 = 0
    norm2 = 0
    
    for key in all_keys:
        val1 = features1.get(key, 0)
        val2 = features2.get(key, 0)
        
        dot_product += val1 * val2
        norm1 += val1 * val1
        norm2 += val2 * val2
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (np.sqrt(norm1) * np.sqrt(norm2))
    return max(0, similarity)  # Ensure non-negative


def validate_product_data(product_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate product data for analysis
    
    Args:
        product_data: Product data dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['product_id', 'title', 'price']
    
    for field in required_fields:
        if field not in product_data:
            return False, f"Missing required field: {field}"
    
    # Validate price
    try:
        price = float(product_data['price'])
        if price < 0:
            return False, "Price must be non-negative"
    except (ValueError, TypeError):
        return False, "Price must be a valid number"
    
    # Validate product_id
    if not product_data['product_id'] or not str(product_data['product_id']).strip():
        return False, "Product ID cannot be empty"
    
    # Validate title
    if not product_data['title'] or not str(product_data['title']).strip():
        return False, "Product title cannot be empty"
    
    return True, ""


def validate_order_data(order_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate order data for analysis
    
    Args:
        order_data: Order data dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['order_id', 'total_amount', 'line_items']
    
    for field in required_fields:
        if field not in order_data:
            return False, f"Missing required field: {field}"
    
    # Validate total_amount
    try:
        total_amount = float(order_data['total_amount'])
        if total_amount < 0:
            return False, "Total amount must be non-negative"
    except (ValueError, TypeError):
        return False, "Total amount must be a valid number"
    
    # Validate line_items
    if not isinstance(order_data['line_items'], list):
        return False, "Line items must be a list"
    
    if len(order_data['line_items']) == 0:
        return False, "Order must have at least one line item"
    
    # Validate each line item
    for i, item in enumerate(order_data['line_items']):
        if not isinstance(item, dict):
            return False, f"Line item {i} must be a dictionary"
        
        if 'productId' not in item and 'product_id' not in item:
            return False, f"Line item {i} must have productId or product_id"
    
    return True, ""


def format_similarity_score(score: float) -> str:
    """
    Format similarity score for display
    
    Args:
        score: Similarity score between 0 and 1
        
    Returns:
        Formatted string
    """
    percentage = score * 100
    return f"{percentage:.1f}%"


def get_similarity_level(score: float) -> str:
    """
    Get similarity level based on score
    
    Args:
        score: Similarity score between 0 and 1
        
    Returns:
        Similarity level (High, Medium, Low)
    """
    if score >= 0.8:
        return "High"
    elif score >= 0.5:
        return "Medium"
    else:
        return "Low"
