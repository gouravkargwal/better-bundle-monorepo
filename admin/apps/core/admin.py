"""
Core admin configuration
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User


# Customize the admin site
admin.site.site_header = "BetterBundle Admin"
admin.site.site_title = "BetterBundle Admin Portal"
admin.site.index_title = "Welcome to BetterBundle Administration"
