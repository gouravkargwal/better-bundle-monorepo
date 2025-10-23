"""
Views for billing app
"""

from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from apps.core.mixins import (
    BaseDashboardView,
    BaseListView,
    BaseDetailView,
    DateFilterMixin,
)
from .models import BillingCycle, BillingInvoice, ShopSubscription, SubscriptionPlan
from apps.shops.models import Shop


class BillingDashboardView(BaseDashboardView):
    """
    Billing dashboard with overview
    """

    template_name = "admin/billing/billing_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Billing Dashboard",
                "icon": "credit-card",
                "description": "Manage subscriptions, billing cycles, and invoices",
                "stats": self.get_billing_stats(),
            }
        )
        return context

    def get_billing_stats(self):
        """
        Get billing statistics
        """
        try:
            # Billing cycle statistics
            active_cycles = BillingCycle.objects.filter(status="ACTIVE").count()
            completed_cycles = BillingCycle.objects.filter(status="COMPLETED").count()
            cancelled_cycles = BillingCycle.objects.filter(status="CANCELLED").count()

            # Invoice statistics
            pending_invoices = BillingInvoice.objects.filter(status="PENDING").count()
            paid_invoices = BillingInvoice.objects.filter(status="PAID").count()
            overdue_invoices = BillingInvoice.objects.filter(status="OVERDUE").count()
            failed_invoices = BillingInvoice.objects.filter(status="FAILED").count()

            # Revenue statistics
            total_billed = (
                BillingInvoice.objects.aggregate(total=Sum("total_amount"))["total"]
                or 0
            )
            total_paid = (
                BillingInvoice.objects.aggregate(total=Sum("amount_paid"))["total"] or 0
            )
            total_outstanding = total_billed - total_paid

            return [
                {"label": "Active Cycles", "value": active_cycles, "color": "success"},
                {
                    "label": "Pending Invoices",
                    "value": pending_invoices,
                    "color": "warning",
                },
                {
                    "label": "Total Billed",
                    "value": f"${total_billed:.2f}",
                    "color": "primary",
                },
                {
                    "label": "Outstanding",
                    "value": f"${total_outstanding:.2f}",
                    "color": "danger",
                },
            ]
        except Exception:
            # Return default stats if database is not ready
            return [
                {"label": "Active Cycles", "value": "0", "color": "success"},
                {"label": "Pending Invoices", "value": "0", "color": "warning"},
                {"label": "Total Billed", "value": "$0.00", "color": "primary"},
                {"label": "Outstanding", "value": "$0.00", "color": "danger"},
            ]


@method_decorator(staff_member_required, name="dispatch")
class BillingCycleListView(ListView):
    """
    List view for billing cycles
    """

    model = BillingCycle
    template_name = "admin/billing/billing_cycle_list.html"
    context_object_name = "cycles"
    paginate_by = 50

    def get_queryset(self):
        return BillingCycle.objects.select_related("shop_subscription__shop").order_by(
            "-start_date"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status:
            context["cycles"] = context["cycles"].filter(status=status)

        return context


@method_decorator(staff_member_required, name="dispatch")
class BillingInvoiceListView(ListView):
    """
    List view for billing invoices
    """

    model = BillingInvoice
    template_name = "admin/billing/billing_invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 50

    def get_queryset(self):
        return BillingInvoice.objects.select_related(
            "shop_subscription__shop"
        ).order_by("-invoice_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status:
            context["invoices"] = context["invoices"].filter(status=status)

        return context


@method_decorator(staff_member_required, name="dispatch")
class SubscriptionListView(ListView):
    """
    List view for shop subscriptions
    """

    model = ShopSubscription
    template_name = "admin/billing/subscription_list.html"
    context_object_name = "subscriptions"
    paginate_by = 50

    def get_queryset(self):
        return ShopSubscription.objects.select_related(
            "shop", "subscription_plan", "pricing_tier"
        ).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status:
            context["subscriptions"] = context["subscriptions"].filter(status=status)

        return context
