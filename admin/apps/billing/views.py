"""
Views for billing app - Pure Django Admin Approach
All functionality is handled by Django Admin interface
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse


@login_required
@staff_member_required
def billing_dashboard(request):
    """Billing dashboard - redirects to Django admin"""
    return HttpResponseRedirect(reverse("admin:index"))
