"""
Billing admin configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import SubscriptionPlan, PricingTier, ShopSubscription, BillingCycle, BillingInvoice


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'plan_type', 'is_active', 'is_default', 'effective_from', 'effective_to'
    ]
    list_filter = ['plan_type', 'is_active', 'is_default', 'effective_from']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


@admin.register(PricingTier)
class PricingTierAdmin(admin.ModelAdmin):
    list_display = [
        'subscription_plan', 'currency', 'commission_rate', 'trial_threshold_amount',
        'is_active', 'is_default', 'effective_from'
    ]
    list_filter = ['currency', 'is_active', 'is_default', 'subscription_plan']
    search_fields = ['subscription_plan__name', 'currency']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['subscription_plan', 'currency']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('subscription_plan')


@admin.register(ShopSubscription)
class ShopSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'shop', 'subscription_plan', 'status', 'start_date', 'end_date',
        'is_active', 'user_chosen_cap_amount', 'activated_at'
    ]
    list_filter = [
        'status', 'is_active', 'auto_renew', 'start_date', 'activated_at'
    ]
    search_fields = ['shop__shop_domain', 'subscription_plan__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop', 'subscription_plan', 'pricing_tier')


@admin.register(BillingCycle)
class BillingCycleAdmin(admin.ModelAdmin):
    list_display = [
        'shop_subscription', 'cycle_number', 'status', 'start_date', 'end_date',
        'current_cap_amount', 'usage_amount', 'usage_percentage_display', 'commission_count'
    ]
    list_filter = ['status', 'start_date', 'end_date', 'activated_at']
    search_fields = ['shop_subscription__shop__shop_domain']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-start_date']
    
    def usage_percentage_display(self, obj):
        """Display usage percentage with color coding"""
        percentage = obj.usage_percentage
        color = 'red' if percentage > 90 else 'orange' if percentage > 75 else 'green'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, percentage
        )
    usage_percentage_display.short_description = 'Usage %'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop_subscription__shop')


@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'shop_subscription', 'invoice_number', 'status', 'total_amount',
        'amount_paid', 'outstanding_amount_display', 'invoice_date', 'due_date', 'paid_at'
    ]
    list_filter = [
        'status', 'invoice_date', 'due_date', 'paid_at', 'currency'
    ]
    search_fields = [
        'shop_subscription__shop__shop_domain', 'invoice_number', 'shopify_invoice_id'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-invoice_date']
    
    def outstanding_amount_display(self, obj):
        """Display outstanding amount with color coding"""
        outstanding = obj.outstanding_amount
        color = 'red' if outstanding > 0 else 'green'
        return format_html(
            '<span style="color: {};">${:.2f}</span>',
            color, outstanding
        )
    outstanding_amount_display.short_description = 'Outstanding'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop_subscription__shop')