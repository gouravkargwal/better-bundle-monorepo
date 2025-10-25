"""
Views for shops app - Pure Django Admin Approach
All functionality is handled by Django Admin interface
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required


@login_required
@staff_member_required
def admin_dashboard(request):
    """Simple dashboard redirect to Django admin"""
    from django.http import HttpResponseRedirect
    from django.urls import reverse

    return HttpResponseRedirect(reverse("admin:index"))
