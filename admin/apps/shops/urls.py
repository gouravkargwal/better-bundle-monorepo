"""
URL patterns for shops app - Pure Django Admin Approach
"""

from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from . import views

app_name = "shops"

urlpatterns = [
    # API endpoints for shop suspension management
    path(
        "api/check-and-suspend-shops/",
        views.check_and_suspend_shops_api,
        name="check_and_suspend_shops_api",
    ),
    path(
        "api/shops-suspension-status/",
        views.get_shops_suspension_status,
        name="get_shops_suspension_status",
    ),
]
