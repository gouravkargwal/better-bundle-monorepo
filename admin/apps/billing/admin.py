"""
Billing admin configuration
"""

import json
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q, Max
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from decimal import Decimal
from .models import (
    SubscriptionPlan,
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
            .select_related("shop", "subscription_plan")
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
    ]
    list_filter = ["status", "start_date", "end_date", "activated_at"]
    search_fields = ["shop_subscription__shop__shop_domain"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-start_date"]
    actions = []


    def usage_percentage_display(self, obj):
        """Display usage percentage with color coding"""
        percentage = obj.usage_percentage
        color = "red" if percentage > 90 else "orange" if percentage > 75 else "green"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)

    usage_percentage_display.short_description = "Usage %"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("shop_subscription__shop")


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


# Predefined jobs the admin dashboard knows about (commission-based jobs removed — flat-rate billing)
SCHEDULED_JOBS = [
    {
        "name": "process-billing",
        "label": "Process Monthly Billing",
        "group": "billing",
        "description": "Calculate charges, create invoices, and record usage to Shopify for all active subscriptions. Runs once per billing period via external cron.",
        "interval_display": "Once per billing period",
        "auto_runs": False,  # Triggered by external cron
        "params_required": False,
    },
]


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
