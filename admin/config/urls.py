"""
URL configuration for BetterBundle Admin Dashboard - Pure Django Admin Approach
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseRedirect
from django.urls import reverse


def admin_redirect(request):
    """Redirect to Django admin"""
    return HttpResponseRedirect(reverse("admin:index"))


urlpatterns = [
    # Main dashboard - redirects to Django admin
    path("", admin_redirect, name="index"),
    path("dashboard/", admin_redirect, name="dashboard"),
    # Django admin - this is our main interface
    path("admin/", admin.site.urls),
    # App URLs - all functionality is in Django admin
    path("shops/", include("apps.shops.urls")),
    path("billing/", include("apps.billing.urls")),
    path("revenue/", include("apps.revenue.urls")),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
