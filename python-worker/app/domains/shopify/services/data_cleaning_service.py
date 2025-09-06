"""
Data Cleaning Service for BetterBundle Python Worker

This service handles the cleaning and normalization of extracted field data
before storage in main tables.
"""

from datetime import datetime
from typing import Dict, Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class DataCleaningService:
    """Service for cleaning and normalizing extracted field data"""

    def __init__(self):
        self.logger = logger

    def clean_data_generic(
        self, data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Generic data cleaning method that handles common patterns"""
        try:
            # Common field cleaning patterns
            cleaning_rules = {
                "orders": {
                    "numeric_fields": [
                        "totalAmount",
                        "subtotalAmount",
                        "totalTaxAmount",
                        "totalShippingAmount",
                        "totalRefundedAmount",
                        "totalOutstandingAmount",
                    ],
                    "date_fields": ["orderDate", "processedAt", "cancelledAt"],
                    "boolean_fields": ["confirmed", "test"],
                    "tag_fields": ["tags"],
                    "defaults": {"currencyCode": "USD"},
                },
                "products": {
                    "numeric_fields": [
                        "price",
                        "compareAtPrice",
                        "totalInventory",
                        "inventory",
                    ],
                    "date_fields": ["productCreatedAt", "productUpdatedAt"],
                    "boolean_fields": ["isActive"],
                    "tag_fields": ["tags"],
                    "array_fields": ["images", "metafields"],
                    "defaults": {"productType": "Unknown", "status": "ACTIVE"},
                },
                "customers": {
                    "numeric_fields": ["totalSpent", "orderCount"],
                    "date_fields": ["lastOrderDate", "createdAt"],
                    "boolean_fields": ["verifiedEmail", "taxExempt"],
                    "tag_fields": ["tags"],
                    "array_fields": ["addresses"],
                    "defaults": {"currencyCode": "USD"},
                },
                "collections": {
                    "date_fields": ["createdAt", "updatedAt"],
                    "boolean_fields": ["isAutomated"],
                    "tag_fields": ["tags"],
                    "defaults": {"bodyHtml": ""},
                },
            }

            rules = cleaning_rules.get(data_type, {})
            cleaned_data = data.copy()

            # Apply numeric field conversions
            for field in rules.get("numeric_fields", []):
                if field in cleaned_data and cleaned_data[field] is not None:
                    if not isinstance(cleaned_data[field], (int, float)):
                        try:
                            if field in ["totalInventory", "orderCount", "inventory"]:
                                cleaned_data[field] = int(cleaned_data[field])
                            else:
                                cleaned_data[field] = float(cleaned_data[field])
                        except (ValueError, TypeError) as e:
                            self.logger.warning(
                                f"Failed to convert {data_type} field '{field}' to numeric: {cleaned_data[field]} - {str(e)}"
                            )
                            cleaned_data[field] = (
                                0
                                if field
                                in ["totalInventory", "orderCount", "inventory"]
                                else 0.0
                            )

            # Apply date field conversions
            for field in rules.get("date_fields", []):
                if field in cleaned_data and cleaned_data[field] is not None:
                    original_value = cleaned_data[field]
                    parsed_date = self._parse_datetime_global(cleaned_data[field])
                    if parsed_date is None and original_value is not None:
                        self.logger.warning(
                            f"Failed to parse {data_type} date field '{field}': {original_value}"
                        )
                    cleaned_data[field] = parsed_date

            # Apply boolean field conversions
            for field in rules.get("boolean_fields", []):
                if field in cleaned_data:
                    cleaned_data[field] = self._parse_boolean(cleaned_data[field])

            # Apply tag field conversions (string to array)
            for field in rules.get("tag_fields", []):
                if field in cleaned_data:
                    tags = cleaned_data[field]
                    if isinstance(tags, str):
                        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
                    elif not isinstance(tags, list):
                        tags = []
                    cleaned_data[field] = tags

            # Apply array field defaults
            for field in rules.get("array_fields", []):
                if cleaned_data.get(field) is None:
                    cleaned_data[field] = []

            # Apply default values
            for field, default_value in rules.get("defaults", {}).items():
                if not cleaned_data.get(field):
                    cleaned_data[field] = default_value

            return cleaned_data

        except Exception as e:
            self.logger.warning(f"Failed to clean {data_type} data: {str(e)}")
            return data

    def _parse_datetime_global(self, date_value: Any) -> Optional[datetime]:
        """Parse various date formats to datetime object"""
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                # Handle ISO format with Z suffix
                if date_value.endswith("Z"):
                    date_value = date_value.replace("Z", "+00:00")
                return datetime.fromisoformat(date_value)
            except (ValueError, TypeError):
                self.logger.warning(f"Failed to parse datetime: {date_value}")
                return None

        return None

    def _parse_boolean(self, bool_value: Any) -> bool:
        """Parse various boolean representations to bool"""
        if bool_value is None:
            return False

        if isinstance(bool_value, bool):
            return bool_value

        if isinstance(bool_value, str):
            return bool_value.lower() in ("true", "1", "yes", "on")

        if isinstance(bool_value, (int, float)):
            return bool(bool_value)

        return False
