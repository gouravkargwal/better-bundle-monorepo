"""
Revenue admin configuration
"""

from django.contrib import admin
from django.db.models import Sum
from .models import PurchaseAttribution


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