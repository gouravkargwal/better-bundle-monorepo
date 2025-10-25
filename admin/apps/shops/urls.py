"""
URL patterns for shops app - Pure Django Admin Approach
"""

from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin

app_name = "shops"

urlpatterns = [
    # All functionality is handled by Django Admin
    # No custom views needed
]
