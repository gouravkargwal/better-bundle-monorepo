"""
Revenue models for BetterBundle Admin Dashboard
⚠️  CRITICAL: Matches the exact schema created by Python worker
Django should NEVER create these tables - they already exist!
"""

from django.db import models
from django.db.models import Sum
from apps.core.models import BaseModel
import json


class SafeJSONField(models.JSONField):
    """JSON field that handles corrupted data gracefully"""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value
        except (TypeError, ValueError, json.JSONDecodeError):
            # Return the raw value if it can't be parsed
            return value

    def to_python(self, value):
        if value is None:
            return value
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value
        except (TypeError, ValueError, json.JSONDecodeError):
            # Return the raw value if it can't be parsed
            return value


class PurchaseAttribution(BaseModel):
    """
    Purchase attribution model
    Matches python-worker/app/core/database/models/purchase_attribution.py
    """

    session_id = models.CharField(max_length=255, db_index=True)
    order_id = models.CharField(max_length=255, db_index=True)
    contributing_extensions = SafeJSONField()
    attribution_weights = SafeJSONField()
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2)
    attributed_revenue = SafeJSONField()
    total_interactions = models.IntegerField()
    interactions_by_extension = SafeJSONField()
    purchase_at = models.DateTimeField(db_index=True)
    attribution_algorithm = models.CharField(max_length=50)
    metadata = SafeJSONField(null=True, blank=True)
    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="purchase_attributions"
    )
    customer_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "purchase_attributions"
        ordering = ["-purchase_at"]
        verbose_name = "Purchase Attribution"
        verbose_name_plural = "Purchase Attributions"

    def __str__(self):
        return f"Attribution {self.id} - {self.shop.shop_domain} - {self.order_id}"
