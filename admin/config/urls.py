"""
URL configuration for BetterBundle Admin Dashboard
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import (
    custom_login,
    custom_logout,
    admin_dashboard,
    AdminDashboardView,
)

urlpatterns = [
    # Authentication
    path("login/", custom_login, name="login"),
    path("logout/", custom_logout, name="logout"),
    # Main dashboard
    path("", admin_dashboard, name="index"),
    path("dashboard/", admin_dashboard, name="dashboard"),
    # Django admin
    path("admin/", admin.site.urls),
    # App URLs
    path("shops/", include("apps.shops.urls")),
    path("billing/", include("apps.billing.urls")),
    path("revenue/", include("apps.revenue.urls")),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
