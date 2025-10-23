"""
Shop models for BetterBundle Admin Dashboard
⚠️  CRITICAL: Matches the exact schema created by Python worker
Django should NEVER create these tables - they already exist!
"""

from django.db import models
from django.db.models import Sum, Count
from apps.core.models import BaseModel


class Shop(BaseModel):
    """
    Shop model representing a Shopify store
    Matches python-worker/app/core/database/models/shop.py
    """

    shop_domain = models.CharField(max_length=255, unique=True, db_index=True)
    custom_domain = models.CharField(max_length=255, null=True, blank=True)
    access_token = models.CharField(max_length=1000)
    plan_type = models.CharField(max_length=50, default="Free", db_index=True)
    currency_code = models.CharField(max_length=10, null=True, blank=True)
    money_format = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    onboarding_completed = models.BooleanField(default=False)
    shopify_plus = models.BooleanField(default=False, db_index=True)
    suspended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    suspension_reason = models.CharField(max_length=255, null=True, blank=True)
    service_impact = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    last_analysis_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "shops"
        ordering = ["-created_at"]
        verbose_name = "Shop"
        verbose_name_plural = "Shops"

    def __str__(self):
        return f"{self.shop_domain} ({self.plan_type})"

    @property
    def subscription_status(self):
        """Get the current subscription status"""
        try:
            return self.shop_subscriptions.status
        except:
            return "No Subscription"

    @property
    def total_revenue(self):
        """Calculate total revenue from commission records"""
        from apps.revenue.models import CommissionRecord

        result = CommissionRecord.objects.filter(shop=self).aggregate(
            total=Sum("commission_earned")
        )
        return result["total"] or 0

    @property
    def total_orders(self):
        """Get total number of orders"""
        return self.order_data.count()

    @property
    def total_products(self):
        """Get total number of products"""
        return self.product_data.count()

    @property
    def total_customers(self):
        """Get total number of customers"""
        return self.customer_data.count()


class OrderData(BaseModel):
    """
    Order data model
    Matches python-worker/app/core/database/models/order_data.py
    """

    order_id = models.CharField(max_length=255, db_index=True)
    order_name = models.CharField(max_length=100, null=True, blank=True)
    customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    customer_phone = models.CharField(max_length=50, null=True, blank=True)
    customer_display_name = models.CharField(max_length=255, null=True, blank=True)
    customer_state = models.CharField(
        max_length=50, null=True, blank=True, db_index=True
    )
    customer_verified_email = models.BooleanField(null=True, blank=True)
    customer_default_address = models.JSONField(null=True, blank=True)
    total_amount = models.FloatField(db_index=True)
    subtotal_amount = models.FloatField(null=True, blank=True)
    total_tax_amount = models.FloatField(null=True, blank=True)
    total_shipping_amount = models.FloatField(null=True, blank=True)
    total_refunded_amount = models.FloatField(null=True, blank=True)
    total_outstanding_amount = models.FloatField(null=True, blank=True)
    order_date = models.DateTimeField(db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=500, null=True, blank=True)
    order_locale = models.CharField(max_length=10, default="en", null=True, blank=True)
    currency_code = models.CharField(
        max_length=10, default="USD", null=True, blank=True, db_index=True
    )
    presentment_currency_code = models.CharField(
        max_length=10, default="USD", null=True, blank=True
    )
    confirmed = models.BooleanField(default=False)
    test = models.BooleanField(default=False)
    financial_status = models.CharField(
        max_length=50, null=True, blank=True, db_index=True
    )
    fulfillment_status = models.CharField(
        max_length=50, null=True, blank=True, db_index=True
    )
    order_status = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    tags = models.JSONField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    note_attributes = models.JSONField(null=True, blank=True)
    shipping_address = models.JSONField(null=True, blank=True)
    billing_address = models.JSONField(null=True, blank=True)
    discount_applications = models.JSONField(null=True, blank=True)
    metafields = models.JSONField(null=True, blank=True)
    fulfillments = models.JSONField(null=True, blank=True)
    transactions = models.JSONField(null=True, blank=True)
    extras = models.JSONField(null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="order_data")

    class Meta:
        db_table = "order_data"
        ordering = ["-order_date"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"Order {self.order_id} - {self.shop.shop_domain}"


class ProductData(BaseModel):
    """
    Product data model
    Matches python-worker/app/core/database/models/product_data.py
    """

    product_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=500)
    handle = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    product_type = models.CharField(max_length=100, null=True, blank=True)
    vendor = models.CharField(max_length=255, null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    total_inventory = models.IntegerField(null=True, blank=True)
    price = models.FloatField()
    compare_at_price = models.FloatField(null=True, blank=True)
    price_range = models.JSONField(null=True, blank=True)
    collections = models.JSONField(null=True, blank=True)
    seo_title = models.CharField(max_length=500, null=True, blank=True)
    seo_description = models.TextField(null=True, blank=True)
    template_suffix = models.CharField(max_length=100, null=True, blank=True)
    variants = models.JSONField(null=True, blank=True)
    images = models.JSONField(null=True, blank=True)
    media = models.JSONField(null=True, blank=True)
    options = models.JSONField(null=True, blank=True)
    metafields = models.JSONField(null=True, blank=True)
    extras = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="product_data"
    )

    class Meta:
        db_table = "product_data"
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return f"{self.title} - {self.shop.shop_domain}"


class CustomerData(BaseModel):
    """
    Customer data model
    Matches python-worker/app/core/database/models/customer_data.py
    """

    customer_id = models.CharField(max_length=255, db_index=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    total_spent = models.FloatField()
    order_count = models.IntegerField()
    last_order_date = models.DateTimeField(null=True, blank=True)
    last_order_id = models.CharField(max_length=100, null=True, blank=True)
    verified_email = models.BooleanField()
    tax_exempt = models.BooleanField()
    customer_locale = models.CharField(max_length=10, null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    default_address = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField()
    extras = models.JSONField(null=True, blank=True)
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="customer_data"
    )

    class Meta:
        db_table = "customer_data"
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.shop.shop_domain}"
