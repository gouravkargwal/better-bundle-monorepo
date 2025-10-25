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


class CommissionRecord(BaseModel):
    """
    Commission record model
    Matches python-worker/app/core/database/models/commission.py
    """

    STATUS_CHOICES = [
        ("TRIAL_PENDING", "Trial Pending"),
        ("TRIAL_COMPLETED", "Trial Completed"),
        ("PENDING", "Pending"),
        ("RECORDED", "Recorded"),
        ("INVOICED", "Invoiced"),
        ("REJECTED", "Rejected"),
        ("FAILED", "Failed"),
        ("CAPPED", "Capped"),
    ]

    BILLING_PHASE_CHOICES = [
        ("TRIAL", "Trial"),
        ("PAID", "Paid"),
    ]

    CHARGE_TYPE_CHOICES = [
        ("FULL", "Full"),
        ("PARTIAL", "Partial"),
        ("OVERFLOW_ONLY", "Overflow Only"),
        ("TRIAL", "Trial"),
        ("REJECTED", "Rejected"),
    ]

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.CASCADE, related_name="commission_records"
    )
    purchase_attribution = models.OneToOneField(
        "PurchaseAttribution",
        on_delete=models.CASCADE,
        related_name="commission_record",
    )
    billing_cycle = models.ForeignKey(
        "billing.BillingCycle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_records",
    )
    order_id = models.CharField(max_length=255, db_index=True)
    order_date = models.DateTimeField(db_index=True)
    attributed_revenue = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4)
    commission_earned = models.DecimalField(max_digits=10, decimal_places=2)
    commission_charged = models.DecimalField(max_digits=10, decimal_places=2)
    commission_overflow = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle_start = models.DateTimeField(null=True, blank=True)
    billing_cycle_end = models.DateTimeField(null=True, blank=True)
    cycle_usage_before = models.DecimalField(max_digits=10, decimal_places=2)
    cycle_usage_after = models.DecimalField(max_digits=10, decimal_places=2)
    capped_amount = models.DecimalField(max_digits=10, decimal_places=2)
    trial_accumulated = models.DecimalField(max_digits=10, decimal_places=2)
    billing_phase = models.CharField(max_length=10, choices=BILLING_PHASE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES)
    shopify_usage_record_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )
    shopify_recorded_at = models.DateTimeField(null=True, blank=True)
    shopify_response = SafeJSONField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    notes = models.TextField(null=True, blank=True)
    commission_metadata = SafeJSONField(null=True, blank=True)
    error_count = models.IntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "commission_records"
        ordering = ["-order_date"]
        verbose_name = "Commission Record"
        verbose_name_plural = "Commission Records"

    def __str__(self):
        return f"Commission {self.id} - {self.shop.shop_domain} - {self.order_id}"
