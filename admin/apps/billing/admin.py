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
    PricingTier,
    ShopSubscription,
    BillingCycle,
    BillingInvoice,
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
    actions = ["sync_from_shopify_and_fix"]

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
