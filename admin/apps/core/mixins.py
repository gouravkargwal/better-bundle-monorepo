"""
Reusable mixins for BetterBundle Admin Dashboard
"""

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import TemplateView, ListView, DetailView
from django.utils import timezone
from datetime import datetime


class AdminRequiredMixin:
    """
    Mixin to require admin authentication for all views
    """

    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class DashboardMixin:
    """
    Mixin to provide common dashboard functionality
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add common dashboard data
        context.update(
            {
                "current_time": timezone.now(),
                "user": self.request.user,
            }
        )

        return context


class DateFilterMixin:
    """
    Mixin to provide date filtering functionality
    """

    def get_date_filters(self):
        """
        Get date filters from request
        """
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                start_date = None

        if end_date:
            try:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                end_date = None

        return start_date, end_date


class BaseDashboardView(AdminRequiredMixin, DashboardMixin, TemplateView):
    """
    Base dashboard view with common functionality
    """

    template_name = "admin/base_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.get_page_title()
        return context

    def get_page_title(self):
        """
        Override in subclasses to set page title
        """
        return "Dashboard"


class BaseListView(AdminRequiredMixin, ListView):
    """
    Base list view with common functionality
    """

    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.get_page_title()
        return context

    def get_page_title(self):
        """
        Override in subclasses to set page title
        """
        return "List View"


class BaseDetailView(AdminRequiredMixin, DetailView):
    """
    Base detail view with common functionality
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.get_page_title()
        return context

    def get_page_title(self):
        """
        Override in subclasses to set page title
        """
        return "Detail View"
