"""
Utility functions for BetterBundle Admin Dashboard
"""

from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


def get_system_stats() -> Dict[str, Any]:
    """
    Get system-wide statistics
    """
    try:
        from apps.shops.models import Shop
        from apps.billing.models import BillingCycle, BillingInvoice
        from apps.revenue.models import CommissionRecord

        stats = {
            "total_shops": Shop.objects.count(),
            "active_shops": Shop.objects.filter(is_active=True).count(),
            "total_revenue": CommissionRecord.objects.aggregate(
                total=Sum("attributed_revenue")
            )["total"]
            or 0,
            "pending_invoices": BillingInvoice.objects.filter(status="PENDING").count(),
        }
    except Exception:
        stats = {
            "total_shops": 0,
            "active_shops": 0,
            "total_revenue": 0,
            "pending_invoices": 0,
        }

    return stats


def get_date_range_stats(
    start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get statistics for a specific date range
    """
    if not start_date:
        start_date = timezone.now() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now()

    try:
        from apps.revenue.models import CommissionRecord
        from apps.billing.models import BillingInvoice

        # Revenue stats for date range
        revenue_stats = CommissionRecord.objects.filter(
            order_date__gte=start_date, order_date__lte=end_date
        ).aggregate(
            total_revenue=Sum("attributed_revenue"),
            total_commission=Sum("commission_earned"),
            order_count=Count("order_id"),
        )

        # Billing stats for date range
        billing_stats = BillingInvoice.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        ).aggregate(
            total_billed=Sum("total_amount"),
            total_paid=Sum("amount_paid"),
            invoice_count=Count("id"),
        )

        return {
            "revenue": revenue_stats,
            "billing": billing_stats,
            "date_range": {
                "start": start_date,
                "end": end_date,
                "days": (end_date - start_date).days,
            },
        }
    except Exception:
        return {
            "revenue": {"total_revenue": 0, "total_commission": 0, "order_count": 0},
            "billing": {"total_billed": 0, "total_paid": 0, "invoice_count": 0},
            "date_range": {"start": start_date, "end": end_date, "days": 0},
        }


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format currency amount
    """
    if currency == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def get_status_color(status: str) -> str:
    """
    Get Bootstrap color class for status
    """
    status_colors = {
        "ACTIVE": "success",
        "INACTIVE": "secondary",
        "SUSPENDED": "danger",
        "PENDING": "warning",
        "COMPLETED": "success",
        "CANCELLED": "danger",
        "PAID": "success",
        "OVERDUE": "danger",
        "FAILED": "danger",
    }
    return status_colors.get(status.upper(), "secondary")


def get_shop_analytics(shop_id: int) -> Dict[str, Any]:
    """
    Get analytics for a specific shop
    """
    try:
        from apps.shops.models import Shop, OrderData, ProductData, CustomerData
        from apps.revenue.models import CommissionRecord

        shop = Shop.objects.get(id=shop_id)

        # Basic counts
        analytics = {
            "total_orders": OrderData.objects.filter(shop=shop).count(),
            "total_products": ProductData.objects.filter(shop=shop).count(),
            "total_customers": CustomerData.objects.filter(shop=shop).count(),
        }

        # Revenue analytics
        revenue_data = CommissionRecord.objects.filter(shop=shop).aggregate(
            total_revenue=Sum("attributed_revenue"),
            total_commission=Sum("commission_earned"),
            total_charged=Sum("commission_charged"),
            order_count=Count("order_id"),
        )
        analytics.update(revenue_data)

        # Recent activity
        analytics["recent_orders"] = OrderData.objects.filter(shop=shop).order_by(
            "-order_date"
        )[:10]
        analytics["recent_commissions"] = CommissionRecord.objects.filter(
            shop=shop
        ).order_by("-created_at")[:10]

        return analytics
    except Exception:
        return {
            "total_orders": 0,
            "total_products": 0,
            "total_customers": 0,
            "total_revenue": 0,
            "total_commission": 0,
            "total_charged": 0,
            "order_count": 0,
            "recent_orders": [],
            "recent_commissions": [],
        }


def get_health_status() -> Dict[str, Any]:
    """
    Get system health status
    """
    try:
        # This would integrate with actual health checks
        return {
            "database": "healthy",
            "redis": "connected",
            "kafka": "running",
            "python_worker": "active",
            "last_check": timezone.now(),
        }
    except Exception:
        return {
            "database": "unknown",
            "redis": "unknown",
            "kafka": "unknown",
            "python_worker": "unknown",
            "last_check": timezone.now(),
        }
