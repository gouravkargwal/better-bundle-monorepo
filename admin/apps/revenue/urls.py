"""
URL patterns for revenue app
"""

from django.urls import path
from . import views

app_name = 'revenue'

urlpatterns = [
    path('', views.RevenueDashboardView.as_view(), name='revenue_dashboard'),
    path('commissions/', views.CommissionListView.as_view(), name='commission_list'),
    path('attributions/', views.AttributionListView.as_view(), name='attribution_list'),
    path('analytics/', views.RevenueAnalyticsView.as_view(), name='revenue_analytics'),
]
