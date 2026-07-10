"""
Revenue admin configuration
"""

import requests
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Sum
from django.conf import settings
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
    
    actions = ["retry_failed_commission"]

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

    def retry_failed_commission(self, request, queryset):
        """
        Retry failed/rejected commissions by resetting them to PENDING
        and publishing a Kafka event for reprocessing.

        Use this when a Shopify usage recording failed temporarily
        and you want to retry without manual DB manipulation.

        Select commissions with status=REJECTED or status=FAILED.
        """
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_URL", "http://localhost:8001"
        )

        retried = 0
        already_pending = 0
        for commission in queryset:
            if commission.status not in ["REJECTED", "FAILED"]:
                already_pending += 1
                continue

            # Reset status to PENDING
            commission.status = "PENDING"
            commission.error_count = 0
            commission.last_error = None
            commission.last_error_at = None
            commission.save()

            # Publish Kafka event for the consumer to pick up
            if commission.billing_cycle_id:
                try:
                    requests.post(
                        f"{python_worker_url}/api/billing/shop/reprocess-rejected-commissions",
                        json={
                            "shop_id": str(commission.shop_id),
                            "billing_cycle_id": str(commission.billing_cycle_id),
                        },
                        timeout=10,
                    )
                except Exception:
                    pass  # Commission is already PENDING — Kafka will pick it up eventually

            retried += 1

        if retried:
            self.message_user(
                request,
                f"✅ Reset {retried} commissions to PENDING for retry. "
                f"If {already_pending} were already pending — no action needed.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"ℹ️ No commissions were retried — {already_pending} were not REJECTED or FAILED",
                level=messages.INFO,
            )

    retry_failed_commission.short_description = "🔄 Retry Failed/Rejected Commission"


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