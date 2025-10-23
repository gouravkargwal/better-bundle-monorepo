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
                Q(shop_domain__icontains=search) | Q(shop_name__icontains=search)
            )

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

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

        # Get analytics data
        context["total_orders"] = shop.order_data.count()
        context["total_products"] = shop.product_data.count()
        context["total_customers"] = shop.customer_data.count()

        # Revenue data
        revenue_data = shop.commission_records.aggregate(
            total_commission=Sum("commission_earned"),
            total_attributed=Sum("attributed_revenue"),
            total_charged=Sum("commission_charged"),
        )
        context.update(revenue_data)

        # Recent activity
        context["recent_orders"] = shop.order_data.order_by("-order_date")[:10]
        context["recent_commissions"] = shop.commission_records.order_by("-created_at")[
            :10
        ]

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

        # Revenue summary
        context["total_attributed"] = (
            commissions.aggregate(total=Sum("attributed_revenue"))["total"] or 0
        )
        context["total_commission"] = (
            commissions.aggregate(total=Sum("commission_earned"))["total"] or 0
        )
        context["total_charged"] = (
            commissions.aggregate(total=Sum("commission_charged"))["total"] or 0
        )

        # Recent commissions
        context["recent_commissions"] = commissions.order_by("-order_date")[:20]

        return context


@method_decorator(staff_member_required, name="dispatch")
class ShopAnalyticsView(DetailView):
    """
    Shop analytics
    """

    model = Shop
    template_name = "admin/shops/shop_analytics.html"
    context_object_name = "shop"
    pk_url_kwarg = "shop_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()

        # Analytics data
        context["total_orders"] = shop.order_data.count()
        context["total_products"] = shop.product_data.count()
        context["total_customers"] = shop.customer_data.count()

        # Revenue analytics
        context["total_revenue"] = (
            shop.commission_records.aggregate(total=Sum("commission_earned"))["total"]
            or 0
        )

        # Recent orders
        context["recent_orders"] = shop.order_data.order_by("-order_date")[:10]

        return context
