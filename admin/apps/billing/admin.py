"""
Billing admin configuration
"""

import json
import requests
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q, Max
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.urls import path, reverse
from django.shortcuts import render
from datetime import timedelta
from decimal import Decimal
from .models import (
    SubscriptionPlan,
    PricingTier,
    ShopSubscription,
    BillingCycle,
    BillingInvoice,
    SchedulerJobExecution,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "plan_type",
        "is_active",
        "is_default",
        "effective_from",
        "effective_to",
    ]
    list_filter = ["plan_type", "is_active", "is_default", "effective_from"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["name"]


@admin.register(PricingTier)
class PricingTierAdmin(admin.ModelAdmin):
    list_display = [
        "subscription_plan",
        "currency",
        "commission_rate",
        "trial_threshold_amount",
        "is_active",
        "is_default",
        "effective_from",
    ]
    list_filter = ["currency", "is_active", "is_default", "subscription_plan"]
    search_fields = ["subscription_plan__name", "currency"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["subscription_plan", "currency"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("subscription_plan")


@admin.register(ShopSubscription)
class ShopSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "shop",
        "subscription_plan",
        "status",
        "start_date",
        "end_date",
        "is_active",
        "user_chosen_cap_amount",
        "activated_at",
        "has_active_cycle",
    ]
    list_filter = ["status", "is_active", "auto_renew", "start_date", "activated_at"]
    search_fields = ["shop__shop_domain", "subscription_plan__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
    actions = [
        "sync_from_shopify_and_fix",
        "force_activate_subscription",
        "increase_subscription_cap",
        "create_billing_cycle_for_subscription",
    ]

    def get_queryset(self, request):
        """Override to show subscriptions with proper eager loading"""
        qs = (
            super()
            .get_queryset(request)
            .select_related("shop", "subscription_plan", "pricing_tier")
        )
        # Show all subscriptions - admin can filter by status if needed
        return qs

    def has_active_cycle(self, obj):
        """Check if subscription has an active billing cycle"""
        from .models import BillingCycle

        has_cycle = BillingCycle.objects.filter(
            shop_subscription=obj, status="ACTIVE"
        ).exists()

        if obj.status == "ACTIVE" and not has_cycle:
            return format_html('<span style="color: red;">❌ Missing</span>')
        elif has_cycle:
            return format_html('<span style="color: green;">✅ Yes</span>')
        else:
            return format_html('<span style="color: gray;">N/A</span>')

    has_active_cycle.short_description = "Active Cycle"

    def sync_from_shopify_and_fix(self, request, queryset):
        """
        🔄 Sync subscription data from Shopify and create billing cycles

        This action:
        1. Calls Python worker API to sync from Shopify
        2. Fetches real cap amount and current usage from Shopify
        3. Creates billing cycle with synced data
        4. Ensures data consistency between Shopify and local database

        ⚠️ Requires:
        - Python worker must be running
        - Shop must have valid access_token
        - Shopify subscription must exist
        """
        import httpx
        from django.conf import settings

        # Get shop IDs from selected subscriptions
        shop_ids = list(
            queryset.filter(status="ACTIVE").values_list("shop_id", flat=True)
        )

        if not shop_ids:
            self.message_user(
                request, "No ACTIVE subscriptions selected", messages.WARNING
            )
            return

        # Call Python worker API
        try:
            # Get API URL from settings or use default
            api_url = getattr(settings, "PYTHON_WORKER_URL", "http://localhost:8001")

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{api_url}/sync-billing-cycles",
                    json=shop_ids,  # Send list directly, not wrapped in object
                )

                if response.status_code == 200:
                    data = response.json()

                    # Show individual results
                    for result in data.get("results", []):
                        if result["success"]:
                            msg = result["message"]
                            if result.get("cap_amount"):
                                msg += f" (cap: ${result['cap_amount']}, usage: ${result['current_usage']})"
                            self.message_user(
                                request,
                                f"✅ {result['shop_domain']}: {msg}",
                                messages.SUCCESS,
                            )
                        else:
                            self.message_user(
                                request,
                                f"❌ {result['shop_domain']}: {result['message']}",
                                (
                                    messages.ERROR
                                    if result.get("error")
                                    else messages.WARNING
                                ),
                            )

                    # Summary
                    summary_parts = []
                    if data["synced"] > 0:
                        summary_parts.append(f"✅ {data['synced']} synced")
                    if data["skipped"] > 0:
                        summary_parts.append(f"ℹ️ {data['skipped']} skipped")
                    if data["errors"] > 0:
                        summary_parts.append(f"❌ {data['errors']} errors")

                    if summary_parts:
                        self.message_user(
                            request,
                            f"Sync complete: {', '.join(summary_parts)}",
                            messages.SUCCESS if data["synced"] > 0 else messages.INFO,
                        )
                else:
                    self.message_user(
                        request,
                        f"API error: {response.status_code} - {response.text}",
                        messages.ERROR,
                    )

        except httpx.RequestError as e:
            self.message_user(
                request,
                f"❌ Failed to connect to Python worker: {str(e)}. Is it running?",
                messages.ERROR,
            )
        except Exception as e:
            self.message_user(request, f"❌ Fatal error: {str(e)}", messages.ERROR)

    sync_from_shopify_and_fix.short_description = (
        "🔄 Sync from Shopify & create billing cycles"
    )

    def force_activate_subscription(self, request, queryset):
        """
        Force-activate a subscription.

        Use this when a merchant says "I approved billing but it's not working."
        This sets status=ACTIVE and is_active=True directly — bypasses the normal
        Shopify webhook flow.

        ⚠️ Only use when you've verified the Shopify subscription is ACTIVE.
        """
        count = 0
        for sub in queryset:
            if sub.status in ["TRIAL", "SUSPENDED"]:
                sub.status = "ACTIVE"
                sub.is_active = True
                sub.activated_at = timezone.now()
                sub.updated_at = timezone.now()
                sub.save()
                count += 1
                self.message_user(
                    request,
                    f"✅ {sub.shop.shop_domain}: Activated (was {sub.get_status_display()})",
                    level=messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    f"ℹ️ {sub.shop.shop_domain}: Already {sub.get_status_display()} — no action",
                    level=messages.INFO,
                )

        if count:
            self.message_user(
                request, f"🎯 Force-activated {count} subscriptions", level=messages.SUCCESS
            )

    force_activate_subscription.short_description = "✅ Force-Activate Subscription"

    def increase_subscription_cap(self, request, queryset):
        """
        Increase the cap for selected subscriptions.

        This action:
        1. Shows a dialog to enter the new cap amount
        2. Updates user_chosen_cap_amount on the subscription
        3. Also updates current_cap_amount on the active billing cycle
        4. Publishes a cap_increase Kafka event to reprocess rejected commissions

        Use this when a merchant requests a cap increase via support.
        """
        if queryset.count() > 1:
            self.message_user(
                request, "⚠️ Please select only one subscription at a time for cap increases",
                level=messages.WARNING,
            )
            return

        sub = queryset.first()
        if not sub:
            return

        # Check for ?new_cap=X URL parameter
        new_cap = request.GET.get("new_cap")
        if new_cap:
            try:
                new_cap_decimal = Decimal(new_cap)
                old_cap = sub.user_chosen_cap_amount or Decimal("0")
                sub.user_chosen_cap_amount = new_cap_decimal
                sub.save()

                # Also update the active billing cycle
                active_cycle = sub.billing_cycles.filter(status="ACTIVE").first()
                if active_cycle:
                    active_cycle.current_cap_amount = new_cap_decimal
                    active_cycle.save()

                    # Call Python worker to publish cap increase event
                    python_worker_url = getattr(settings, "PYTHON_WORKER_URL", "http://localhost:8001")
                    try:
                        requests.post(
                            f"{python_worker_url}/api/billing/jobs/trigger/reprocess-rejected",
                            json={"shop_id": str(sub.shop_id)},
                            timeout=10,
                        )
                    except Exception:
                        pass  # Non-blocking — cap is already updated

                self.message_user(
                    request,
                    f"✅ {sub.shop.shop_domain}: Cap increased from ${old_cap:.2f} to ${new_cap_decimal:.2f}",
                    level=messages.SUCCESS,
                )
            except (ValueError, Decimal.InvalidOperation):
                self.message_user(
                    request,
                    f"❌ Invalid cap amount: {new_cap}. Use a number like 5000.00",
                    level=messages.ERROR,
                )
        else:
            # Tell the admin to add the cap as a URL parameter and retry
            self.message_user(
                request,
                f"ℹ️ To increase cap for {sub.shop.shop_domain}, re-run this action with "
                f"?new_cap=5000.00 in the URL (e.g., .../admin/billing/shopsubscription/"
                f"?new_cap=5000.00)",
                level=messages.INFO,
            )

    increase_subscription_cap.short_description = "💰 Increase Cap (add ?new_cap=X to URL)"

    def create_billing_cycle_for_subscription(self, request, queryset):
        """
        Create a billing cycle for subscriptions that are ACTIVE but missing one.
        """
        created = 0
        for sub in queryset:
            has_active = sub.billing_cycles.filter(status="ACTIVE").exists()
            if has_active:
                self.message_user(
                    request,
                    f"ℹ️ {sub.shop.shop_domain}: Already has an active cycle",
                    level=messages.INFO,
                )
                continue

            if sub.status not in ["ACTIVE", "TRIAL"]:
                self.message_user(
                    request,
                    f"⚠️ {sub.shop.shop_domain}: Status is {sub.get_status_display()}, not ACTIVE or TRIAL",
                    level=messages.WARNING,
                )
                continue

            # Determine the next cycle number
            existing_cycles = sub.billing_cycles.all()
            next_number = (existing_cycles.aggregate(Max("cycle_number"))["cycle_number__max"] or 0) + 1

            cap = sub.user_chosen_cap_amount or Decimal("1000")

            # Create the cycle
            sub.billing_cycles.create(
                cycle_number=next_number,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
                initial_cap_amount=cap,
                current_cap_amount=cap,
                usage_amount=Decimal("0"),
                commission_count=0,
                status="ACTIVE",
                activated_at=timezone.now(),
            )
            created += 1
            self.message_user(
                request,
                f"✅ {sub.shop.shop_domain}: Created billing cycle #{next_number} with cap ${cap:.2f}",
                level=messages.SUCCESS,
            )

        if created:
            self.message_user(
                request, f"🎯 Created {created} billing cycles", level=messages.SUCCESS
            )

    create_billing_cycle_for_subscription.short_description = "🔄 Create Billing Cycle (if missing)"


@admin.register(BillingCycle)
class BillingCycleAdmin(admin.ModelAdmin):
    list_display = [
        "shop_subscription",
        "cycle_number",
        "status",
        "start_date",
        "end_date",
        "current_cap_amount",
        "usage_amount",
        "usage_percentage_display",
        "commission_count",
    ]
    list_filter = ["status", "start_date", "end_date", "activated_at"]
    search_fields = ["shop_subscription__shop__shop_domain"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-start_date"]
    actions = ["increase_cycle_cap"]

    def usage_percentage_display(self, obj):
        """Display usage percentage with color coding"""
        percentage = obj.usage_percentage
        color = "red" if percentage > 90 else "orange" if percentage > 75 else "green"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)

    usage_percentage_display.short_description = "Usage %"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("shop_subscription__shop")

    def increase_cycle_cap(self, request, queryset):
        """
        Increase the current cap amount on selected billing cycles.

        Add ?new_cap=X to the URL when triggering this action.
        If no URL param is provided, shows instructions.
        """
        new_cap = request.GET.get("new_cap")
        if not new_cap:
            self.message_user(
                request,
                "ℹ️ To increase cap, re-run this action with ?new_cap=5000.00 in the URL",
                level=messages.INFO,
            )
            return

        try:
            new_cap_decimal = Decimal(new_cap)
        except (ValueError, Decimal.InvalidOperation):
            self.message_user(
                request, f"❌ Invalid cap amount: {new_cap}", level=messages.ERROR
            )
            return

        updated = 0
        for cycle in queryset:
            old_cap = cycle.current_cap_amount
            cycle.current_cap_amount = new_cap_decimal
            cycle.updated_at = timezone.now()
            cycle.save()
            updated += 1
            self.message_user(
                request,
                f"✅ {cycle}: Cap ${old_cap:.2f} → ${new_cap_decimal:.2f}",
                level=messages.SUCCESS,
            )

        if updated:
            self.message_user(
                request, f"🎯 Updated cap on {updated} billing cycles", level=messages.SUCCESS
            )

    increase_cycle_cap.short_description = "💰 Increase Cycle Cap (add ?new_cap=X to URL)"


@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "shop_subscription",
        "invoice_number",
        "status",
        "total_amount",
        "amount_paid",
        "outstanding_amount_display",
        "invoice_date",
        "due_date",
        "paid_at",
    ]
    list_filter = ["status", "invoice_date", "due_date", "paid_at", "currency"]
    search_fields = [
        "shop_subscription__shop__shop_domain",
        "invoice_number",
        "shopify_invoice_id",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-invoice_date"]

    def outstanding_amount_display(self, obj):
        """Display outstanding amount with color coding"""
        outstanding = obj.outstanding_amount
        color = "red" if outstanding > 0 else "green"
        return format_html(
            '<span style="color: {};">${:.2f}</span>', color, outstanding
        )

    outstanding_amount_display.short_description = "Outstanding"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("shop_subscription__shop")


# =====================================================================
# SCHEDULER / CRON JOB MANAGEMENT
# =====================================================================


# Predefined jobs the admin dashboard knows about
SCHEDULED_JOBS = [
    {
        "name": "reconcile-stuck-commissions",
        "label": "Reconcile Stuck Commissions",
        "group": "billing",
        "description": "Finds commissions stuck in RECORDING status and marks them RECORDED (if Shopify succeeded) or resets to PENDING (if Shopify failed). Runs automatically every 5 minutes.",
        "interval_display": "Every 5 minutes",
        "auto_runs": True,
        "params_required": False,
    },
    {
        "name": "process-billing",
        "label": "Process Monthly Billing",
        "group": "billing",
        "description": "Calculate charges, create invoices, and record usage to Shopify for all active subscriptions. Runs once per billing period via external cron.",
        "interval_display": "Once per billing period",
        "auto_runs": False,  # Triggered by external cron
        "params_required": False,
    },
    {
        "name": "reprocess-rejected",
        "label": "Reprocess Rejected Commissions",
        "group": "billing",
        "description": "Re-evaluate REJECTED commissions against the current cap and re-record them to Shopify if cap space is available. Requires a shop_id.",
        "interval_display": "On demand",
        "auto_runs": False,
        "params_required": True,
    },
]


def _get_python_worker_url():
    """Get the Python worker API base URL from settings."""
    from django.conf import settings

    return getattr(settings, "PYTHON_WORKER_URL", "http://localhost:8001")


def _fetch_last_executions(limit: int = 50) -> list:
    """Fetch recent job executions from the Python worker API."""
    try:
        url = f"{_get_python_worker_url()}/api/billing/jobs/last-executions?limit={limit}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def _fetch_last_run_for_job(job_name: str) -> dict | None:
    """Fetch the most recent execution for a specific job."""
    try:
        url = f"{_get_python_worker_url()}/api/billing/jobs/last-run/{job_name}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data if data else None
    except Exception:
        pass
    return None


def _trigger_job(job_name: str, shop_id: str = None) -> dict:
    """Trigger a job manually via the Python worker API."""
    try:
        url = f"{_get_python_worker_url()}/api/billing/jobs/trigger/{job_name}"
        body = {}
        if shop_id:
            body["shop_id"] = shop_id
        resp = requests.post(url, json=body, timeout=120)
        if resp.status_code == 200:
            return resp.json()
        return {"success": False, "message": f"API error: {resp.status_code} - {resp.text[:200]}"}
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Request timed out after 120s"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@admin.register(SchedulerJobExecution)
class SchedulerJobExecutionAdmin(admin.ModelAdmin):
    """
    Admin view for SchedulerJobExecution — shows the run history of all
    scheduled/background jobs.
    """

    list_display = [
        "job_name",
        "status_colored",
        "started_at",
        "duration_display",
        "triggered_by",
        "items_processed",
        "result_summary_short",
    ]
    list_filter = ["status", "job_name", "job_group", "triggered_by", "started_at"]
    search_fields = ["job_name", "result_summary", "error_message"]
    readonly_fields = [
        "id",
        "job_name",
        "job_group",
        "started_at",
        "completed_at",
        "duration_ms",
        "status",
        "success",
        "result_summary",
        "error_message",
        "error_details",
        "triggered_by",
        "attempt_number",
        "items_processed",
        "metadata_json",
        "created_at",
    ]
    ordering = ["-started_at"]
    date_hierarchy = "started_at"
    list_per_page = 50

    def has_add_permission(self, request):
        """Job executions are created automatically — no manual add."""
        return False

    def has_change_permission(self, request, obj=None):
        """Job executions are read-only — no manual editing."""
        return False

    def status_colored(self, obj):
        """Color-coded status badge"""
        colors = {
            "RUNNING": "#2196F3",
            "SUCCESS": "#4CAF50",
            "FAILED": "#F44336",
            "SKIPPED": "#9E9E9E",
        }
        color = colors.get(obj.status, "#666")
        return format_html(
            '<span style="color: {}; font-weight: bold;">&#9679; {}</span>',
            color,
            obj.get_status_display() if hasattr(obj, "get_status_display") else obj.status,
        )

    status_colored.short_description = "Status"

    def duration_display(self, obj):
        """Human-readable duration"""
        if obj.duration_ms is None:
            return "—"
        seconds = obj.duration_ms / 1000
        if seconds < 60:
            return f"{seconds:.1f}s"
        return f"{seconds / 60:.1f}m"

    duration_display.short_description = "Duration"

    def result_summary_short(self, obj):
        """Truncated result summary for list view"""
        if not obj.result_summary:
            return "—"
        return obj.result_summary[:80] + ("..." if len(obj.result_summary) > 80 else "")

    result_summary_short.short_description = "Result"

    fieldsets = (
        (
            "Job Identity",
            {
                "fields": ("job_name", "job_group", "triggered_by", "attempt_number"),
            },
        ),
        (
            "Timing",
            {
                "fields": ("started_at", "completed_at", "duration_ms"),
            },
        ),
        (
            "Outcome",
            {
                "fields": ("status", "success", "items_processed", "result_summary"),
            },
        ),
        (
            "Errors",
            {
                "fields": ("error_message", "error_details"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("metadata_json", "created_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_urls(self):
        """Add scheduler dashboard URLs to this admin page."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.scheduler_dashboard_view),
                name="billing_scheduler_dashboard",
            ),
            path(
                "trigger/<job_name>/",
                self.admin_site.admin_view(self.scheduler_trigger_job),
                name="billing_scheduler_trigger",
            ),
        ]
        return custom_urls + urls

    def scheduler_dashboard_view(self, request):
        """
        Render the scheduler dashboard page showing all known jobs,
        their last run status, and manual trigger buttons.
        """
        last_executions = _fetch_last_executions(limit=100)

        # Build per-job stats
        job_stats = {}
        for job_def in SCHEDULED_JOBS:
            job_name = job_def["name"]
            executions = [e for e in last_executions if e.get("job_name") == job_name]
            last_run = executions[0] if executions else None

            total_runs = len(executions)
            success_count = sum(1 for e in executions if e.get("success") is True)
            failure_count = sum(1 for e in executions if e.get("success") is False)

            job_stats[job_name] = {
                "definition": job_def,
                "last_run": last_run,
                "total_runs": total_runs,
                "success_count": success_count,
                "failure_count": failure_count,
                "recent_success": last_run and last_run.get("success") is True,
                "last_run_display": self._format_run_display(last_run),
            }

        # Recent activity across all jobs
        all_executions = sorted(
            last_executions,
            key=lambda e: e.get("started_at", ""),
            reverse=True,
        )[:30]

        context = {
            **self.admin_site.each_context(request),
            "title": "Scheduler Dashboard",
            "job_stats": job_stats,
            "recent_executions": all_executions,
            "opts": self.model._meta,
            "available_apps": self.admin_site.get_app_list(request),
        }
        return render(request, "admin/billing/scheduler_dashboard.html", context)

    def scheduler_trigger_job(self, request, job_name: str):
        """
        Handle a manual job trigger from the scheduler dashboard.
        """
        shop_id = request.GET.get("shop_id")
        result = _trigger_job(job_name, shop_id=shop_id)

        if result.get("success"):
            self.message_user(
                request,
                f"✅ {job_name}: {result.get('message', 'Triggered successfully')} "
                f"({result.get('duration_ms', '?')}ms)",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"❌ {job_name}: {result.get('message', 'Failed to trigger')}",
                level=messages.ERROR,
            )

        return HttpResponseRedirect(reverse("admin:billing_scheduler_dashboard"))

    def _format_run_display(self, execution: dict | None) -> str:
        """Format a run record for display."""
        if not execution:
            return "Never run"

        started = execution.get("started_at", "")
        status = execution.get("status", "")
        duration = execution.get("duration_ms")

        parts = [started[:19].replace("T", " ") if started else "?"]
        if status:
            parts.append(f"[{status}]")
        if duration:
            parts.append(f"({duration / 1000:.1f}s)")

        return " ".join(parts)
