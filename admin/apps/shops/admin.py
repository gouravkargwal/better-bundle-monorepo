"""
Shop admin configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from .models import Shop, OrderData, ProductData, CustomerData


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = [
        'shop_domain', 'plan_type', 'is_active', 'onboarding_completed',
        'subscription_status', 'total_revenue_display', 'total_orders', 
        'total_products', 'last_analysis_at', 'created_at'
    ]
    list_filter = [
        'is_active', 'onboarding_completed', 'shopify_plus', 'plan_type',
        'created_at', 'last_analysis_at', 'suspended_at'
    ]
    search_fields = ['shop_domain', 'email', 'custom_domain']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('shop_domain', 'custom_domain', 'email', 'plan_type')
        }),
        ('Status', {
            'fields': ('is_active', 'onboarding_completed', 'shopify_plus')
        }),
        ('Suspension', {
            'fields': ('suspended_at', 'suspension_reason', 'service_impact'),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': ('last_analysis_at', 'currency_code', 'money_format'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def subscription_status(self, obj):
        """Display subscription status with color coding"""
        try:
            status = obj.shop_subscriptions.status
            color = {
                'ACTIVE': 'green',
                'TRIAL': 'orange',
                'SUSPENDED': 'red',
                'CANCELLED': 'gray',
            }.get(status, 'black')
            return format_html(
                '<span style="color: {};">{}</span>',
                color, status
            )
        except:
            return format_html('<span style="color: red;">No Subscription</span>')
    subscription_status.short_description = 'Subscription Status'

    def total_revenue_display(self, obj):
        """Display total revenue with formatting"""
        revenue = obj.total_revenue
        return f"${revenue:,.2f}"
    total_revenue_display.short_description = 'Total Revenue'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop_subscriptions')


@admin.register(OrderData)
class OrderDataAdmin(admin.ModelAdmin):
    list_display = [
        'order_id', 'shop', 'order_date', 'total_amount', 'currency_code',
        'financial_status', 'fulfillment_status', 'customer_display_name'
    ]
    list_filter = [
        'financial_status', 'fulfillment_status', 'order_status', 'currency_code',
        'order_date', 'confirmed', 'test'
    ]
    search_fields = ['order_id', 'order_name', 'customer_id', 'shop__shop_domain']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-order_date']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop')


@admin.register(ProductData)
class ProductDataAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'shop', 'product_id', 'price', 'product_type', 'vendor',
        'is_active', 'total_inventory', 'created_at'
    ]
    list_filter = [
        'is_active', 'product_type', 'vendor', 'created_at'
    ]
    search_fields = ['title', 'product_id', 'shop__shop_domain', 'vendor']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop')


@admin.register(CustomerData)
class CustomerDataAdmin(admin.ModelAdmin):
    list_display = [
        'first_name', 'last_name', 'shop', 'customer_id', 'total_spent',
        'order_count', 'last_order_date', 'verified_email', 'is_active'
    ]
    list_filter = [
        'verified_email', 'tax_exempt', 'is_active', 'state', 'created_at'
    ]
    search_fields = ['first_name', 'last_name', 'customer_id', 'shop__shop_domain']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop')