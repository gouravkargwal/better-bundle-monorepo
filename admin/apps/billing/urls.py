"""
URL patterns for billing app - Pure Django Admin Approach
"""

from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    # All functionality is handled by Django Admin
    # No custom views needed
]
