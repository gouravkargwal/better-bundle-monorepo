"""
Core views for BetterBundle Admin Dashboard - Pure Django Admin Approach
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse


def custom_login(request):
    """
    Custom login view - redirects to Django admin login
    """
    if request.user.is_authenticated:
        return redirect("admin:index")

    # Use Django's built-in admin login
    return redirect("admin:login")


@login_required
def custom_logout(request):
    """
    Custom logout view
    """
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("admin:login")


@login_required
def admin_dashboard(request):
    """
    Main admin dashboard - redirects to Django admin
    """
    return HttpResponseRedirect(reverse("admin:index"))
