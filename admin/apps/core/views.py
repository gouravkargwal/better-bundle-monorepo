"""
Core views for BetterBundle Admin Dashboard
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .mixins import BaseDashboardView


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
        context.update(
            {
                "icon": "tachometer-alt",
                "description": "System overview and quick actions",
                "stats": [
                    {"label": "Active Shops", "value": "0", "color": "info"},
                    {"label": "Revenue Today", "value": "0.00", "color": "primary"},
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
