"""
Billing admin configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import (
    SubscriptionPlan,
    ShopSubscription,
    BillingCycle,
    BillingInvoice,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "plan_type",
        "monthly_fee",
        "discount_percentage",
        "effective_monthly_fee_display",
        "is_active",
        "is_default",
        "trial_days",
        "effective_from",
        "effective_to",
    ]
    list_filter = ["plan_type", "is_active", "is_default", "effective_from"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["name"]

    def effective_monthly_fee_display(self, obj):
        """Show effective monthly fee after discount"""
        if not obj.monthly_fee:
            return "—"
        fee = Decimal(obj.monthly_fee)
        if obj.discount_percentage:
            fee = fee * (1 - Decimal(obj.discount_percentage) / 100)
        return f"${fee:.2f}"

    effective_monthly_fee_display.short_description = "Effective Fee"


@admin.register(ShopSubscription)
class ShopSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "shop",
        "subscription_plan",
        "status",
        "pricing_type_display",
        "effective_fee_display",
        "trial_status_display",
        "start_date",
        "end_date",
        "is_active",
        "has_active_cycle",
    ]
    list_filter = ["status", "is_active", "auto_renew", "start_date", "activated_at"]
    search_fields = ["shop__shop_domain", "subscription_plan__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
    actions = ["sync_from_shopify_and_fix"]

    fieldsets = [
        (
            "Shop & Plan",
            {
                "fields": ["shop", "subscription_plan"],
            },
        ),
        (
            "Status",
            {
                "fields": ["status", "is_active", "auto_renew"],
            },
        ),
        (
            "Dates",
            {
                "fields": [
                    "start_date",
                    "end_date",
                    "activated_at",
                    "suspended_at",
                    "cancelled_at",
                ],
            },
        ),
        (
            "Flat Fee Settings",
            {
                "classes": ["wide"],
                "fields": ["monthly_fee_override", "trial_duration_days"],
                "description": "Override plan defaults for this specific shop",
            },
        ),
        (
            "Metadata",
            {
                "fields": ["subscription_metadata"],
            },
        ),
    ]

    def get_queryset(self, request):
        """Override to show subscriptions with proper eager loading"""
        qs = super().get_queryset(request).select_related("shop", "subscription_plan")
        return qs

    def pricing_type_display(self, obj):
        """Show flat fee vs usage-based badge"""
        if obj.is_flat_fee:
            return format_html(
                '<span style="background: #DCFCE7; color: #166534; padding: 2px 8px; '
                'border-radius: 4px;">Flat Fee</span>'
            )
        return format_html(
            '<span style="background: #FEF3C7; color: #92400E; padding: 2px 8px; '
            'border-radius: 4px;">Usage-Based</span>'
        )

    pricing_type_display.short_description = "Type"

    def effective_fee_display(self, obj):
        """Show effective monthly fee"""
        if obj.is_flat_fee:
            fee = obj.effective_monthly_fee
            if fee:
                return format_html(
                    '<span style="font-weight: 600;">${}</span>',
                    f"{fee:.2f}" if isinstance(fee, Decimal) else fee,
                )
            return "—"
        return "—"

    effective_fee_display.short_description = "Fee / Cap"

    def trial_status_display(self, obj):
        """Show trial days remaining for flat fee trials"""
        if not obj.is_trial:
            return "—"
        if obj.is_flat_fee:
            remaining = obj.trial_remaining_days
            total = obj.effective_trial_days
            if remaining <= 0:
                return format_html(
                    '<span style="color: #DC2626; font-weight: 600;">Expired</span>'
                )
            elif remaining <= 3:
                return format_html(
                    '<span style="color: #D97706; font-weight: 600;">{}d / {}d ⚠️</span>',
                    remaining,
                    total,
                )
            return format_html(
                '<span style="color: #059669;">{}d / {}d</span>',
                remaining,
                total,
            )
        # Legacy trial: show revenue-based status
        return format_html('<span style="color: #6B7280;">Revenue-based</span>')

    trial_status_display.short_description = "Trial Days"

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
                    json=shop_ids,
                )

                if response.status_code == 200:
                    data = response.json()

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


@admin.register(BillingCycle)
class BillingCycleAdmin(admin.ModelAdmin):
    list_display = [
        "shop_subscription",
        "cycle_number",
        "cycle_type_display",
        "status",
        "start_date",
        "end_date",
        "period_fee",
        "current_cap_amount",
        "usage_amount",
        "usage_percentage_display",
        "commission_count",
    ]
    list_filter = ["status", "start_date", "end_date", "activated_at"]
    search_fields = ["shop_subscription__shop__shop_domain"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-start_date"]

    fieldsets = [
        (
            "Basic Info",
            {
                "fields": ["shop_subscription", "cycle_number", "status"],
            },
        ),
        (
            "Dates",
            {
                "fields": [
                    "start_date",
                    "end_date",
                    "activated_at",
                    "completed_at",
                    "cancelled_at",
                ],
            },
        ),
        (
            "Flat Fee",
            {
                "classes": ["wide"],
                "fields": ["period_fee"],
                "description": "For flat fee cycles: the flat fee charged for this period",
            },
        ),
        (
            "Legacy Usage-Based",
            {
                "classes": ["collapse"],
                "fields": [
                    "initial_cap_amount",
                    "current_cap_amount",
                    "usage_amount",
                    "commission_count",
                ],
                "description": "Legacy fields for usage-based billing cycles (historical data)",
            },
        ),
        (
            "Metadata",
            {
                "fields": ["cycle_metadata"],
            },
        ),
    ]

    def cycle_type_display(self, obj):
        """Show cycle type with colored badge"""
        if obj.is_flat_fee_cycle:
            return format_html(
                '<span style="background: #DCFCE7; color: #166534; padding: 2px 8px; '
                'border-radius: 4px; font-weight: 500;">Flat Fee</span>'
            )
        return format_html(
            '<span style="background: #FEF3C7; color: #92400E; padding: 2px 8px; '
            'border-radius: 4px; font-weight: 500;">Usage-Based</span>'
        )

    cycle_type_display.short_description = "Type"

    def usage_percentage_display(self, obj):
        """Display usage percentage with color coding (legacy only)"""
        if obj.is_flat_fee_cycle:
            return format_html('<span style="color: #9CA3AF;">N/A</span>')
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
