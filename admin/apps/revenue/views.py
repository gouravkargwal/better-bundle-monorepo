"""
Views for revenue app
"""

from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.db.models import Sum, Count, Avg
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
from .models import CommissionRecord, PurchaseAttribution
from apps.shops.models import Shop


class RevenueDashboardView(BaseDashboardView, DateFilterMixin):
    """
    Revenue dashboard with overview
    """

    template_name = "admin/revenue/revenue_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Revenue Dashboard",
                "icon": "chart-line",
                "description": "Track revenue, commissions, and purchase attributions",
                "stats": self.get_revenue_stats(),
            }
        )
        return context

    def get_revenue_stats(self):
        """
        Get revenue statistics
        """
        try:
            # Get date filters
            start_date, end_date = self.get_date_filters()

            # Filter commissions by date if provided
            commissions = CommissionRecord.objects.all()
            if start_date:
                commissions = commissions.filter(order_date__gte=start_date)
            if end_date:
                commissions = commissions.filter(order_date__lte=end_date)

            # Revenue summary
            total_attributed = (
                commissions.aggregate(total=Sum("attributed_revenue"))["total"] or 0
            )
            total_commission = (
                commissions.aggregate(total=Sum("commission_earned"))["total"] or 0
            )
            total_charged = (
                commissions.aggregate(total=Sum("commission_charged"))["total"] or 0
            )

            return [
                {
                    "label": "Total Revenue",
                    "value": f"${total_attributed:.2f}",
                    "color": "success",
                },
                {
                    "label": "Commission Earned",
                    "value": f"${total_commission:.2f}",
                    "color": "primary",
                },
                {
                    "label": "Commission Charged",
                    "value": f"${total_charged:.2f}",
                    "color": "warning",
                },
                {
                    "label": "Total Orders",
                    "value": commissions.count(),
                    "color": "info",
                },
            ]
        except Exception:
            # Return default stats if database is not ready
            return [
                {"label": "Total Revenue", "value": "$0.00", "color": "success"},
                {"label": "Commission Earned", "value": "$0.00", "color": "primary"},
                {"label": "Commission Charged", "value": "$0.00", "color": "warning"},
                {"label": "Total Orders", "value": "0", "color": "info"},
            ]


@method_decorator(staff_member_required, name="dispatch")
class CommissionListView(ListView):
    """
    List view for commission records
    """

    model = CommissionRecord
    template_name = "admin/revenue/commission_list.html"
    context_object_name = "commissions"
    paginate_by = 50

    def get_queryset(self):
        queryset = CommissionRecord.objects.select_related("shop", "billing_cycle")

        # Date filtering
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            queryset = queryset.filter(order_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(order_date__lte=end_date)

        return queryset.order_by("-order_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Revenue summary
        queryset = self.get_queryset()
        context["total_attributed"] = (
            queryset.aggregate(total=Sum("attributed_revenue"))["total"] or 0
        )
        context["total_commission"] = (
            queryset.aggregate(total=Sum("commission_earned"))["total"] or 0
        )
        context["total_charged"] = (
            queryset.aggregate(total=Sum("commission_charged"))["total"] or 0
        )

        return context


@method_decorator(staff_member_required, name="dispatch")
class AttributionListView(ListView):
    """
    List view for purchase attributions
    """

    model = PurchaseAttribution
    template_name = "admin/revenue/attribution_list.html"
    context_object_name = "attributions"
    paginate_by = 50

    def get_queryset(self):
        return PurchaseAttribution.objects.select_related("shop").order_by(
            "-purchase_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Attribution summary
        context["total_attributions"] = PurchaseAttribution.objects.count()
        context["total_revenue"] = (
            PurchaseAttribution.objects.aggregate(total=Sum("total_revenue"))["total"]
            or 0
        )

        return context


@method_decorator(staff_member_required, name="dispatch")
class RevenueAnalyticsView(TemplateView):
    """
    Revenue analytics view
    """

    template_name = "admin/revenue/revenue_analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date filters from request
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        # Filter commissions by date if provided
        commissions = CommissionRecord.objects.all()
        if start_date:
            commissions = commissions.filter(order_date__gte=start_date)
        if end_date:
            commissions = commissions.filter(order_date__lte=end_date)

        # Analytics data
        context["total_attributed"] = (
            commissions.aggregate(total=Sum("attributed_revenue"))["total"] or 0
        )
        context["total_commission"] = (
            commissions.aggregate(total=Sum("commission_earned"))["total"] or 0
        )
        context["total_charged"] = (
            commissions.aggregate(total=Sum("commission_charged"))["total"] or 0
        )

        # Shop-wise revenue
        context["shop_revenue"] = (
            commissions.values("shop__shop_domain")
            .annotate(
                total_attributed=Sum("attributed_revenue"),
                total_commission=Sum("commission_earned"),
                total_charged=Sum("commission_charged"),
                order_count=Count("order_id"),
            )
            .order_by("-total_commission")
        )

        # Status breakdown
        context["status_breakdown"] = (
            commissions.values("status")
            .annotate(count=Count("id"), total_commission=Sum("commission_earned"))
            .order_by("-count")
        )

        return context
