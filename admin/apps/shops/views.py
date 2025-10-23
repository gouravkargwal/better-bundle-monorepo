"""
Views for shops app
"""

from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, DetailView
from django.db.models import Sum, Count, Avg, Q
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
from .models import Shop, OrderData, ProductData, CustomerData
from apps.billing.models import ShopSubscription, BillingCycle, BillingInvoice
from apps.revenue.models import CommissionRecord


class ShopListView(BaseListView):
    """
    List view for all shops with enhanced functionality
    """

    model = Shop
    template_name = "admin/shops/shop_list.html"
    context_object_name = "shops"
    paginate_by = 50

    def get_queryset(self):
        queryset = Shop.objects.select_related("shop_subscriptions").all()

        # Search functionality
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(shop_domain__icontains=search)
                | Q(custom_domain__icontains=search)
                | Q(email__icontains=search)
            )

        # Filter by status
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True, suspended_at__isnull=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        elif status == "suspended":
            queryset = queryset.filter(suspended_at__isnull=False)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add summary statistics with error handling
        try:
            context["total_shops"] = Shop.objects.count()
            context["active_shops"] = Shop.objects.filter(is_active=True).count()
            context["onboarded_shops"] = Shop.objects.filter(
                onboarding_completed=True
            ).count()
            context["suspended_shops"] = Shop.objects.filter(
                suspended_at__isnull=False
            ).count()
        except Exception:
            context["total_shops"] = 0
            context["active_shops"] = 0
            context["onboarded_shops"] = 0
            context["suspended_shops"] = 0

        # Add filter state for template
        context["current_status"] = self.request.GET.get("status", "")
        context["current_search"] = self.request.GET.get("search", "")

        # Add selected states for template (formatter-safe)
        context["active_selected"] = (
            " selected" if context["current_status"] == "active" else ""
        )
        context["inactive_selected"] = (
            " selected" if context["current_status"] == "inactive" else ""
        )
        context["suspended_selected"] = (
            " selected" if context["current_status"] == "suspended" else ""
        )

        return context

    def get_page_title(self):
        return "Shops Management"


@method_decorator(staff_member_required, name="dispatch")
class ShopDetailView(DetailView):
    """
    Detail view for a specific shop
    """

    model = Shop
    template_name = "admin/shops/shop_detail.html"
    context_object_name = "shop"
    pk_url_kwarg = "shop_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()

        # Get subscription info
        try:
            subscription = shop.shop_subscriptions
            context["subscription"] = subscription
            context["billing_cycles"] = subscription.billing_cycles.all()[:5]
            context["recent_invoices"] = subscription.billing_invoices.all()[:5]
        except:
            context["subscription"] = None
            context["billing_cycles"] = []
            context["recent_invoices"] = []

        # Get analytics data - with error handling
        try:
            context["total_orders"] = shop.order_data.count()
        except Exception as e:
            context["total_orders"] = 0
            print(f"Error counting orders: {e}")

        try:
            context["total_products"] = shop.product_data.count()
        except Exception as e:
            context["total_products"] = 0
            print(f"Error counting products: {e}")

        try:
            context["total_customers"] = shop.customer_data.count()
        except Exception as e:
            context["total_customers"] = 0
            print(f"Error counting customers: {e}")

        # Revenue data - with error handling
        try:
            revenue_data = shop.commission_records.aggregate(
                total_commission=Sum("commission_earned"),
                total_attributed=Sum("attributed_revenue"),
                total_charged=Sum("commission_charged"),
            )
            context.update(revenue_data)
        except Exception as e:
            context["total_commission"] = 0
            context["total_attributed"] = 0
            context["total_charged"] = 0
            print(f"Error fetching revenue data: {e}")

        # Recent activity - with comprehensive error handling for JSON fields
        context["recent_orders"] = []
        context["recent_commissions"] = []

        try:
            # Use values() to avoid JSON field parsing issues
            recent_orders_data = shop.order_data.values(
                "id",
                "order_id",
                "order_date",
                "total_amount",
                "order_status",
                "financial_status",
            ).order_by("-order_date")[:10]
            context["recent_orders"] = list(recent_orders_data)
        except Exception as e:
            print(f"Error fetching recent orders: {e}")

        try:
            # Use values() to avoid JSON field parsing issues
            recent_commissions_data = shop.commission_records.values(
                "id",
                "order_date",
                "commission_earned",
                "attributed_revenue",
                "commission_charged",
                "status",
            ).order_by("-created_at")[:10]
            context["recent_commissions"] = list(recent_commissions_data)
        except Exception as e:
            print(f"Error fetching recent commissions: {e}")

        return context


@method_decorator(staff_member_required, name="dispatch")
class ShopSubscriptionView(DetailView):
    """
    Shop subscription details
    """

    model = Shop
    template_name = "admin/shops/shop_subscription.html"
    context_object_name = "shop"
    pk_url_kwarg = "shop_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()

        try:
            subscription = shop.shop_subscriptions
            context["subscription"] = subscription
            context["trial"] = getattr(subscription, "subscription_trial", None)
            context["shopify_subscription"] = getattr(
                subscription, "shopify_subscription", None
            )
            context["billing_cycles"] = subscription.billing_cycles.all()
        except:
            context["subscription"] = None
            context["trial"] = None
            context["shopify_subscription"] = None
            context["billing_cycles"] = []

        return context


@method_decorator(staff_member_required, name="dispatch")
class ShopBillingView(DetailView):
    """
    Shop billing details
    """

    model = Shop
    template_name = "admin/shops/shop_billing.html"
    context_object_name = "shop"
    pk_url_kwarg = "shop_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()

        try:
            subscription = shop.shop_subscriptions
            context["current_cycle"] = subscription.billing_cycles.filter(
                status="ACTIVE"
            ).first()
            context["billing_history"] = subscription.billing_cycles.all()
            context["invoices"] = subscription.billing_invoices.all()
        except:
            context["current_cycle"] = None
            context["billing_history"] = []
            context["invoices"] = []

        return context


@method_decorator(staff_member_required, name="dispatch")
class ShopInvoicesView(DetailView):
    """
    Shop invoices
    """

    model = Shop
    template_name = "admin/shops/shop_invoices.html"
    context_object_name = "shop"
    pk_url_kwarg = "shop_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()

        try:
            subscription = shop.shop_subscriptions
            context["invoices"] = subscription.billing_invoices.all()
        except:
            context["invoices"] = []

        return context


@method_decorator(staff_member_required, name="dispatch")
class ShopRevenueView(DetailView):
    """
    Shop revenue details
    """

    model = Shop
    template_name = "admin/shops/shop_revenue.html"
    context_object_name = "shop"
    pk_url_kwarg = "shop_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()

        # Get date filters from request
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        # Filter commissions by date if provided
        commissions = shop.commission_records.all()
        if start_date:
            commissions = commissions.filter(order_date__gte=start_date)
        if end_date:
            commissions = commissions.filter(order_date__lte=end_date)

        # Revenue summary - with error handling
        try:
            context["total_attributed"] = (
                commissions.aggregate(total=Sum("attributed_revenue"))["total"] or 0
            )
        except Exception as e:
            context["total_attributed"] = 0
            print(f"Error calculating total attributed: {e}")

        try:
            context["total_commission"] = (
                commissions.aggregate(total=Sum("commission_earned"))["total"] or 0
            )
        except Exception as e:
            context["total_commission"] = 0
            print(f"Error calculating total commission: {e}")

        try:
            context["total_charged"] = (
                commissions.aggregate(total=Sum("commission_charged"))["total"] or 0
            )
        except Exception as e:
            context["total_charged"] = 0
            print(f"Error calculating total charged: {e}")

        # Recent commissions - with error handling for JSON fields
        context["recent_commissions"] = []
        try:
            # Use values() to avoid JSON field parsing issues
            recent_commissions_data = commissions.values(
                "id",
                "order_date",
                "commission_earned",
                "attributed_revenue",
                "commission_charged",
                "status",
            ).order_by("-order_date")[:20]
            context["recent_commissions"] = list(recent_commissions_data)
        except Exception as e:
            print(f"Error fetching recent commissions: {e}")

        return context
