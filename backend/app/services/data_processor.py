"""
Data processor service for the ML API
"""

from typing import List, Dict, Any, Union
from app.core.logging import get_logger

logger = get_logger(__name__)


class DataProcessor:
    """Service for data processing and transformation operations"""

    def transform_line_items(
        self, line_items: Union[Dict, List, Any]
    ) -> List[Dict[str, Any]]:
        """
        Transform line_items from various formats to a standardized list

        Args:
            line_items: Line items in various formats (GraphQL, list, etc.)

        Returns:
            Standardized list of line item dictionaries
        """
        try:
            if isinstance(line_items, dict) and "edges" in line_items:
                # GraphQL structure: {"edges": [{"node": {...}}]}
                transformed_items = []
                for edge in line_items["edges"]:
                    if "node" in edge:
                        transformed_items.append(edge["node"])
                logger.debug(
                    f"Transformed GraphQL structure: {len(transformed_items)} items"
                )
                return transformed_items

            elif isinstance(line_items, list):
                # Already a list
                logger.debug(
                    f"Line items already in list format: {len(line_items)} items"
                )
                return line_items

            elif line_items is None:
                # No line items
                logger.debug("No line items found")
                return []

            else:
                # Fallback: try to use as-is or convert to list
                logger.warning(f"Unknown line_items format: {type(line_items)}")
                if hasattr(line_items, "__iter__") and not isinstance(line_items, str):
                    return list(line_items)
                else:
                    return [line_items] if line_items else []

        except Exception as e:
            logger.error(f"Error transforming line items: {str(e)}")
            return []

    def validate_product_data(self, product: Dict[str, Any]) -> bool:
        """
        Validate product data structure

        Args:
            product: Product data dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["product_id", "title", "price"]

        for field in required_fields:
            if field not in product:
                logger.warning(f"Missing required field: {field}")
                return False

        # Validate price is numeric and positive
        try:
            price = float(product["price"])
            if price < 0:
                logger.warning(f"Invalid price: {price}")
                return False
        except (ValueError, TypeError):
            logger.warning(f"Invalid price format: {product['price']}")
            return False

        return True

    def validate_order_data(self, order: Dict[str, Any]) -> bool:
        """
        Validate order data structure

        Args:
            order: Order data dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["order_id", "total_amount", "line_items"]

        for field in required_fields:
            if field not in order:
                logger.warning(f"Missing required field: {field}")
                return False

        # Validate total_amount is numeric and positive
        try:
            total = float(order["total_amount"])
            if total < 0:
                logger.warning(f"Invalid total amount: {total}")
                return False
        except (ValueError, TypeError):
            logger.warning(f"Invalid total amount format: {order['total_amount']}")
            return False

        # Validate line_items is a list
        if not isinstance(order["line_items"], list):
            logger.warning("Line items must be a list")
            return False

        return True

    def clean_product_text(self, text: str) -> str:
        """
        Clean and normalize product text data

        Args:
            text: Raw text string

        Returns:
            Cleaned text string
        """
        if not text:
            return ""

        # Convert to string if needed
        text = str(text)

        # Remove extra whitespace
        text = " ".join(text.split())

        # Convert to lowercase for consistency
        text = text.lower()

        return text

    def extract_product_features(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract features from product data for similarity analysis

        Args:
            product: Product data dictionary

        Returns:
            Dictionary of extracted features
        """
        features = {}

        # Text features
        if "title" in product:
            features["title"] = self.clean_product_text(product["title"])

        if "description" in product:
            features["description"] = self.clean_product_text(product["description"])

        if "category" in product:
            features["category"] = self.clean_product_text(product["category"])

        if "tags" in product and isinstance(product["tags"], list):
            features["tags"] = [self.clean_product_text(tag) for tag in product["tags"]]

        # Numerical features
        if "price" in product:
            try:
                features["price"] = float(product["price"])
            except (ValueError, TypeError):
                features["price"] = 0.0

        return features
