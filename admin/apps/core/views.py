"""
Core views for BetterBundle Admin Dashboard
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from .mixins import BaseDashboardView
from apps.shops.models import Shop
from apps.revenue.models import CommissionRecord


def custom_login(request):
    """
    Custom login view with clean layout
    """
    if request.user.is_authenticated:
        return redirect("admin:index")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("admin:index")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "registration/login.html")


@login_required
def custom_logout(request):
    """
    Custom logout view
    """
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("admin:login")


class AdminDashboardView(BaseDashboardView):
    """
    Main admin dashboard with system overview
    """

    template_name = "admin/dashboard.html"

    def get_page_title(self):
        return "Admin Dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get today's date for revenue calculation
        today = timezone.now().date()

        # Fetch real data from database
        try:
            # Active shops count
            active_shops = Shop.objects.filter(
                is_active=True, suspended_at__isnull=True
            ).count()
        except Exception:
            active_shops = 0

        try:
            # Revenue today - get commissions from today
            revenue_today = (
                CommissionRecord.objects.filter(order_date=today).aggregate(
                    total=Sum("attributed_revenue")
                )["total"]
                or 0
            )
        except Exception:
            revenue_today = 0

        try:
            # Total shops count
            total_shops = Shop.objects.count()
        except Exception:
            total_shops = 0

        try:
            # Total revenue (all time)
            total_revenue = (
                CommissionRecord.objects.aggregate(total=Sum("attributed_revenue"))[
                    "total"
                ]
                or 0
            )
        except Exception:
            total_revenue = 0

        context.update(
            {
                "icon": "tachometer-alt",
                "description": "System overview and quick actions",
                "active_shops": active_shops,
                "revenue_today": revenue_today,
                "total_shops": total_shops,
                "total_revenue": total_revenue,
                "stats": [
                    {
                        "label": "Active Shops",
                        "value": str(active_shops),
                        "color": "info",
                    },
                    {
                        "label": "Revenue Today",
                        "value": f"{revenue_today:.2f}",
                        "color": "primary",
                    },
                    {
                        "label": "Total Shops",
                        "value": str(total_shops),
                        "color": "success",
                    },
                    {
                        "label": "Total Revenue",
                        "value": f"{total_revenue:.2f}",
                        "color": "warning",
                    },
                ],
            }
        )
        return context


# Function-based views for backward compatibility
@login_required
def admin_dashboard(request):
    """
    Main admin dashboard (function-based for compatibility)
    """
    view = AdminDashboardView()
    view.request = request
    return view.get(request)
