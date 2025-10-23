"""
URL patterns for shops app
"""

from django.urls import path, include
from . import views

app_name = 'shops'

urlpatterns = [
    path('', views.ShopListView.as_view(), name='shop_list'),
    path('<str:shop_id>/', include([
        path('', views.ShopDetailView.as_view(), name='shop_detail'),
        path('subscription/', views.ShopSubscriptionView.as_view(), name='shop_subscription'),
        path('billing/', views.ShopBillingView.as_view(), name='shop_billing'),
        path('invoices/', views.ShopInvoicesView.as_view(), name='shop_invoices'),
        path('revenue/', views.ShopRevenueView.as_view(), name='shop_revenue'),
        path('analytics/', views.ShopAnalyticsView.as_view(), name='shop_analytics'),
    ])),
]
