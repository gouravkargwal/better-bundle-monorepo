"""
URL patterns for billing app
"""

from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.BillingDashboardView.as_view(), name='billing_dashboard'),
    path('cycles/', views.BillingCycleListView.as_view(), name='billing_cycle_list'),
    path('invoices/', views.BillingInvoiceListView.as_view(), name='billing_invoice_list'),
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription_list'),
]
