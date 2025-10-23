"""
Billing models for BetterBundle Admin Dashboard
⚠️  CRITICAL: Matches the exact schema created by Python worker
Django should NEVER create these tables - they already exist!
"""

from django.db import models
from django.db.models import Sum
from apps.core.models import BaseModel


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
    default_commission_rate = models.CharField(max_length=10, null=True, blank=True)
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


class PricingTier(BaseModel):
    """
    Pricing tier model
    Matches python-worker/app/core/database/models/pricing_tier.py
    """

    subscription_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name="pricing_tiers"
    )
    currency = models.CharField(max_length=3)
    trial_threshold_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    minimum_charge = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    proration_enabled = models.BooleanField(default=False)
    tier_metadata = models.TextField(null=True, blank=True)
    effective_from = models.DateTimeField()
    effective_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pricing_tiers"
        ordering = ["subscription_plan", "currency"]
        verbose_name = "Pricing Tier"
        verbose_name_plural = "Pricing Tiers"

    def __str__(self):
        return f"{self.subscription_plan.name} - {self.currency}"


class ShopSubscription(BaseModel):
    """
    Shop subscription model
    Matches python-worker/app/core/database/models/shop_subscription.py
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
    pricing_tier = models.ForeignKey(
        PricingTier, on_delete=models.CASCADE, related_name="shop_subscriptions"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRIAL")
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=True)
    subscription_metadata = models.TextField(null=True, blank=True)
    user_chosen_cap_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
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


class BillingCycle(BaseModel):
    """
    Billing cycle model
    Matches python-worker/app/core/database/models/billing_cycle.py
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
    initial_cap_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_cap_amount = models.DecimalField(max_digits=10, decimal_places=2)
    usage_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_count = models.IntegerField(default=0)
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
        """Calculate usage percentage"""
        if self.current_cap_amount > 0:
            return (self.usage_amount / self.current_cap_amount) * 100
        return 0


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
