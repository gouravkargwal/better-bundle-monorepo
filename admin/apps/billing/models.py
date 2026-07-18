"""
Billing models for BetterBundle Admin Dashboard
⚠️  CRITICAL: Matches the exact schema created by Python worker
Django should NEVER create these tables - they already exist!
"""

from django.db import models
from django.db.models import Sum
from apps.core.models import BaseModel
from datetime import datetime, timezone


class SubscriptionPlan(BaseModel):
    """
    Subscription plan model
    Matches python-worker/app/core/database/models/subscription_plan.py
    """

    PLAN_TYPE_CHOICES = [
        ("USAGE_BASED", "Usage Based"),
        ("TIERED", "Tiered"),
        ("FLAT_RATE", "Flat Rate"),
        ("HYBRID", "Hybrid"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    monthly_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Flat monthly fee for the plan",
    )
    trial_days = models.IntegerField(
        null=True, blank=True, help_text="Number of days for free trial"
    )
    plan_metadata = models.TextField(null=True, blank=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscription_plans"
        ordering = ["name"]
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"

    def __str__(self):
        return self.name


class ShopSubscription(BaseModel):
    """
    Shop subscription model
    Matches python-worker/app/core/database/models/shop_subscription.py

    Supports both legacy usage-based and new flat fee subscriptions.
    """

    STATUS_CHOICES = [
        ("TRIAL", "Trial"),
        ("PENDING_APPROVAL", "Pending Approval"),
        ("TRIAL_COMPLETED", "Trial Completed"),
        ("ACTIVE", "Active"),
        ("SUSPENDED", "Suspended"),
        ("CANCELLED", "Cancelled"),
        ("EXPIRED", "Expired"),
    ]

    shop = models.OneToOneField(
        "shops.Shop", on_delete=models.CASCADE, related_name="shop_subscriptions"
    )
    subscription_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name="shop_subscriptions"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRIAL")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    subscription_metadata = models.TextField(null=True, blank=True)
    # Flat fee field
    monthly_fee_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Per-shop override of the pricing tier monthly fee",
    )
    trial_duration_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration of the trial in days (for flat fee plans)",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shop_subscriptions"
        ordering = ["-created_at"]
        verbose_name = "Shop Subscription"
        verbose_name_plural = "Shop Subscriptions"

    def __str__(self):
        return f"{self.shop.shop_domain} - {self.subscription_plan.name}"

    @property
    def is_trial(self):
        """Check if subscription is in trial phase"""
        return self.status == "TRIAL"

    @property
    def is_paid(self):
        """Check if subscription is in paid phase"""
        return self.status == "ACTIVE"

    @property
    def effective_monthly_fee(self):
        """Return the effective monthly fee (override > plan default)"""
        if self.monthly_fee_override:
            return self.monthly_fee_override
        if self.subscription_plan and self.subscription_plan.monthly_fee:
            return self.subscription_plan.monthly_fee
        return 0

    @property
    def effective_trial_days(self):
        """Return the effective trial days"""
        if self.trial_duration_days:
            return self.trial_duration_days
        if self.subscription_plan and self.subscription_plan.trial_days:
            return self.subscription_plan.trial_days
        return 14  # Default

    @property
    def trial_remaining_days(self):
        """Calculate remaining trial days based on start date"""
        if not self.is_trial or not self.start_date:
            return 0
        from datetime import timedelta, timezone

        trial_end = self.start_date + timedelta(days=self.effective_trial_days)
        remaining = (trial_end - datetime.now(timezone.utc)).days
        return max(0, remaining)

    @property
    def is_flat_fee(self):
        """Check if this is a flat fee subscription"""
        return self.subscription_plan.plan_type == "FLAT_RATE"


class BillingCycle(BaseModel):
    """
    Billing cycle model
    Matches python-worker/app/core/database/models/billing_cycle.py

    Supports both legacy usage-based and new flat fee billing cycles.
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
        ("SUSPENDED", "Suspended"),
    ]

    shop_subscription = models.ForeignKey(
        ShopSubscription, on_delete=models.CASCADE, related_name="billing_cycles"
    )
    cycle_number = models.IntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    # Legacy usage-based fields (nullable for flat fee)
    initial_cap_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    current_cap_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    usage_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, default=0
    )
    commission_count = models.IntegerField(null=True, blank=True, default=0)
    # Flat fee field
    period_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Flat fee charged for this billing period",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    activated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cycle_metadata = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "billing_cycles"
        ordering = ["-start_date"]
        verbose_name = "Billing Cycle"
        verbose_name_plural = "Billing Cycles"

    def __str__(self):
        return f"Cycle {self.cycle_number} - {self.shop_subscription.shop.shop_domain}"

    @property
    def usage_percentage(self):
        """Calculate usage percentage (legacy usage-based only)"""
        if self.current_cap_amount and self.current_cap_amount > 0:
            usage = self.usage_amount or 0
            return (usage / self.current_cap_amount) * 100
        return 0

    @property
    def is_flat_fee_cycle(self):
        """Check if this is a flat fee billing cycle"""
        return self.period_fee is not None and self.period_fee > 0

    @property
    def cycle_type_display(self):
        """Return human-readable cycle type"""
        if self.is_flat_fee_cycle:
            return f"Flat ${self.period_fee}"
        return "Usage-based"


class ShopifySubscription(BaseModel):
    """
    Shopify subscription model
    Matches python-worker/app/core/database/models/shopify_subscription.py
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("ACTIVE", "Active"),
        ("DECLINED", "Declined"),
        ("CANCELLED", "Cancelled"),
        ("EXPIRED", "Expired"),
        ("FROZEN", "Frozen"),
    ]

    shop_subscription = models.OneToOneField(
        ShopSubscription, on_delete=models.CASCADE, related_name="shopify_subscriptions"
    )
    shopify_subscription_id = models.CharField(max_length=255, unique=True)
    shopify_line_item_id = models.CharField(max_length=255, null=True, blank=True)
    confirmation_url = models.URLField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    error_count = models.CharField(max_length=20, default="0")

    class Meta:
        db_table = "shopify_subscriptions"
        ordering = ["-created_at"]
        verbose_name = "Shopify Subscription"
        verbose_name_plural = "Shopify Subscriptions"

    def __str__(self):
        return f"{self.shop_subscription.shop.shop_domain} - Shopify {self.status}"


class BillingInvoice(BaseModel):
    """
    Billing invoice model
    Matches python-worker/app/core/database/models/billing_invoice.py
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("OVERDUE", "Overdue"),
        ("CANCELLED", "Cancelled"),
        ("REFUNDED", "Refunded"),
        ("FAILED", "Failed"),
    ]

    shop_subscription = models.ForeignKey(
        ShopSubscription, on_delete=models.CASCADE, related_name="billing_invoices"
    )
    shopify_invoice_id = models.CharField(max_length=255, unique=True)
    invoice_number = models.CharField(max_length=100, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    invoice_date = models.DateTimeField()
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    description = models.TextField(null=True, blank=True)
    line_items = models.JSONField(null=True, blank=True)
    shopify_response = models.JSONField(null=True, blank=True)
    payment_method = models.CharField(max_length=100, null=True, blank=True)
    payment_reference = models.CharField(max_length=255, null=True, blank=True)
    failure_reason = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "billing_invoices"
        ordering = ["-invoice_date"]
        verbose_name = "Billing Invoice"
        verbose_name_plural = "Billing Invoices"

    def __str__(self):
        return f"Invoice {self.invoice_number or self.shopify_invoice_id} - {self.shop_subscription.shop.shop_domain}"

    @property
    def outstanding_amount(self):
        """Calculate outstanding amount"""
        return self.total_amount - self.amount_paid
