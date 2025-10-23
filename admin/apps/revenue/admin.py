"""
Revenue admin configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import CommissionRecord, PurchaseAttribution


@admin.register(CommissionRecord)
class CommissionRecordAdmin(admin.ModelAdmin):
    list_display = [
        'shop', 'order_id', 'order_date', 'attributed_revenue', 'commission_earned',
        'commission_charged', 'status', 'billing_phase', 'charge_type', 'created_at'
    ]
    list_filter = [
        'status', 'billing_phase', 'charge_type', 'currency', 'order_date', 'created_at'
    ]
    search_fields = [
        'shop__shop_domain', 'order_id', 'shopify_usage_record_id'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-order_date']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop', 'billing_cycle')
    
    def get_changelist(self, request, **kwargs):
        """Add summary statistics to the changelist"""
        changelist = super().get_changelist(request, **kwargs)
        
        # Add summary statistics
        queryset = self.get_queryset(request)
        summary = queryset.aggregate(
            total_attributed=Sum('attributed_revenue'),
            total_commission=Sum('commission_earned'),
            total_charged=Sum('commission_charged')
        )
        
        # Add summary to context
        changelist.summary = summary
        return changelist


@admin.register(PurchaseAttribution)
class PurchaseAttributionAdmin(admin.ModelAdmin):
    list_display = [
        'shop', 'order_id', 'session_id', 'total_revenue', 'total_interactions',
        'purchase_at', 'attribution_algorithm', 'customer_id'
    ]
    list_filter = [
        'attribution_algorithm', 'purchase_at', 'created_at'
    ]
    search_fields = [
        'shop__shop_domain', 'order_id', 'session_id', 'customer_id'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-purchase_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('shop')