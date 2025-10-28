from django.contrib import admin
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.urls import reverse
from django.db import models
import requests
from django.conf import settings
from .models import Shop, OrderData


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = [
        "shop_domain",
        "plan_type",
        "is_active",
        "total_orders_count",
        "total_products_count",
        "total_customers_count",
        "attribution_health_percentage",
        "revenue_summary",
        "created_at",
    ]
    list_filter = [
        "is_active",
        "plan_type",
        "created_at",
    ]
    search_fields = ["shop_domain", "email"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "total_orders_count",
        "total_products_count",
        "total_customers_count",
        "attribution_health_percentage",
        "revenue_summary",
    ]
    actions = [
        "recalculate_shop_attribution",
        "recalculate_all_attribution",
        "trigger_data_collection",
        "export_shop_data",
        "backfill_customer_links",
        "mark_as_active",
        "mark_as_inactive",
        "check_and_suspend_trial_completed_shops",
    ]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("shop_domain", "email", "plan_type", "is_active")},
        ),
        (
            "Statistics",
            {
                "fields": (
                    "total_orders_count",
                    "total_products_count",
                    "total_customers_count",
                    "attribution_health_percentage",
                    "revenue_summary",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def total_orders_count(self, obj):
        return obj.order_data.count()

    total_orders_count.short_description = "Orders"

    def total_products_count(self, obj):
        return obj.product_data.count()

    total_products_count.short_description = "Products"

    def total_customers_count(self, obj):
        return obj.customer_data.count()

    total_customers_count.short_description = "Customers"

    def attribution_health_percentage(self, obj):
        total_orders = obj.order_data.count()
        if total_orders == 0:
            return "0%"

        orders_with_attribution = obj.purchase_attributions.count()
        percentage = round((orders_with_attribution / total_orders) * 100, 1)

        if percentage >= 90:
            return f"✅ {percentage}%"
        elif percentage >= 70:
            return f"⚠️ {percentage}%"
        else:
            return f"❌ {percentage}%"

    attribution_health_percentage.short_description = "Attribution Health"

    def attribution_health_status(self, obj):
        """Filter method for attribution health status"""
        total_orders = obj.order_data.count()
        if total_orders == 0:
            return "no_orders"

        orders_with_attribution = obj.purchase_attributions.count()
        percentage = (orders_with_attribution / total_orders) * 100

        if percentage >= 90:
            return "excellent"
        elif percentage >= 70:
            return "good"
        else:
            return "poor"

    def revenue_summary(self, obj):
        """Show total revenue and commission"""
        try:
            total_revenue = (
                obj.order_data.aggregate(total=models.Sum("total_amount"))["total"] or 0
            )

            total_commission = (
                obj.purchase_attributions.aggregate(
                    total=models.Sum("attributed_revenue")
                )["total"]
                or 0
            )

            return (
                f"Revenue: ${total_revenue:.2f} | Commission: ${total_commission:.2f}"
            )
        except:
            return "N/A"

    revenue_summary.short_description = "Revenue Summary"

    def recalculate_shop_attribution(self, request, queryset):
        """Django admin action to recalculate attribution for selected shops"""
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_API_URL", "http://localhost:8001"
        )

        for shop in queryset:
            try:
                response = requests.post(
                    f"{python_worker_url}/api/v1/attribution/shop-wide",
                    json={
                        "shop_id": str(shop.id),
                        "force_recalculate": True,
                        "batch_size": 50,
                        "dry_run": False,
                    },
                    timeout=120,
                )

                if response.status_code == 200:
                    data = response.json()
                    self.message_user(
                        request,
                        f"✅ {shop.shop_domain}: Recalculated {data.get('published_events', 0)} events",
                        level=messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"❌ {shop.shop_domain}: Failed - {response.text}",
                        level=messages.ERROR,
                    )
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ {shop.shop_domain}: Error - {str(e)}",
                    level=messages.ERROR,
                )
            except requests.exceptions.Timeout:
                self.message_user(
                    request,
                    f"⏰ {shop.shop_domain}: Timeout - Process may still be running",
                    level=messages.WARNING,
                )

    recalculate_shop_attribution.short_description = "🔄 Recalculate Attribution"

    def recalculate_all_attribution(self, request, queryset):
        """Django admin action to recalculate attribution for all shops"""
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_API_URL", "http://localhost:8001"
        )

        total_shops = queryset.count()
        success_count = 0

        for shop in queryset:
            try:
                response = requests.post(
                    f"{python_worker_url}/api/v1/attribution/shop-wide",
                    json={
                        "shop_id": str(shop.id),
                        "force_recalculate": True,
                        "batch_size": 50,
                        "dry_run": False,
                    },
                    timeout=120,
                )

                if response.status_code == 200:
                    success_count += 1

            except Exception:
                pass  # Continue with other shops

        self.message_user(
            request,
            f"✅ Recalculated attribution for {success_count}/{total_shops} shops",
            level=(
                messages.SUCCESS if success_count == total_shops else messages.WARNING
            ),
        )

    recalculate_all_attribution.short_description = "🔄 Recalculate All Attribution"

    def trigger_data_collection(self, request, queryset):
        """Trigger data collection for selected shops"""
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_API_URL", "http://localhost:8001"
        )
        success_count = 0
        total_shops = queryset.count()

        for shop in queryset:
            try:
                response = requests.post(
                    f"{python_worker_url}/api/v1/data-collection/trigger",
                    json={
                        "shop_id": str(shop.id),
                        "data_types": ["orders", "products", "customers"],
                        "since_hours": 24,
                        "force_refresh": True,
                        "dry_run": False,
                    },
                    timeout=300,  # 5 minutes timeout for data collection
                )

                if response.status_code == 200:
                    result = response.json()
                    success_count += 1
                    self.message_user(
                        request,
                        f"✅ Data collection triggered for {shop.shop_domain}: "
                        f"{result.get('orders_collected', 0)} orders, "
                        f"{result.get('products_collected', 0)} products, "
                        f"{result.get('customers_collected', 0)} customers",
                        level=messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"❌ Failed to trigger data collection for {shop.shop_domain}: "
                        f"{response.status_code}",
                        level=messages.ERROR,
                    )

            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Error triggering data collection for {shop.shop_domain}: {str(e)}",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"🚀 Data collection triggered for {success_count}/{total_shops} shops",
            level=(
                messages.SUCCESS if success_count == total_shops else messages.WARNING
            ),
        )

    trigger_data_collection.short_description = "📥 Trigger Data Collection"

    def backfill_customer_links(self, request, queryset):
        """Backfill customer links for selected shops"""
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_API_URL", "http://localhost:8001"
        )
        success_count = 0
        total_shops = queryset.count()

        for shop in queryset:
            try:
                response = requests.post(
                    f"{python_worker_url}/api/v1/customer-linking/shops/{shop.id}/backfill",
                    json={
                        "shop_id": str(shop.id),
                        "batch_size": 100,
                        "force": True,
                    },
                    timeout=300,  # 5 minutes timeout for customer linking
                )

                if response.status_code == 200:
                    result = response.json()
                    success_count += 1
                    self.message_user(
                        request,
                        f"✅ Customer linking backfill completed for {shop.shop_domain}: "
                        f"{result.get('processed_links', 0)} links processed, "
                        f"{result.get('duration_seconds', 0):.1f}s",
                        level=messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"❌ Failed to backfill customer links for {shop.shop_domain}: "
                        f"{response.status_code} - {response.text}",
                        level=messages.ERROR,
                    )

            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Error backfilling customer links for {shop.shop_domain}: {str(e)}",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"🔗 Customer linking backfill completed for {success_count}/{total_shops} shops",
            level=(
                messages.SUCCESS if success_count == total_shops else messages.WARNING
            ),
        )

    backfill_customer_links.short_description = "🔗 Backfill Customer Links"

    def export_shop_data(self, request, queryset):
        """Export shop data to CSV"""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="shop_data.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Shop Domain",
                "Plan Type",
                "Active",
                "Orders",
                "Products",
                "Customers",
                "Attribution Health",
                "Total Revenue",
            ]
        )

        for shop in queryset:
            total_orders = shop.order_data.count()
            total_products = shop.product_data.count()
            total_customers = shop.customer_data.count()

            attribution_percentage = 0
            if total_orders > 0:
                orders_with_attribution = shop.purchase_attributions.count()
                attribution_percentage = round(
                    (orders_with_attribution / total_orders) * 100, 1
                )

            total_revenue = (
                shop.order_data.aggregate(total=models.Sum("total_amount"))["total"]
                or 0
            )

            writer.writerow(
                [
                    shop.shop_domain,
                    shop.plan_type,
                    "Yes" if shop.is_active else "No",
                    total_orders,
                    total_products,
                    total_customers,
                    f"{attribution_percentage}%",
                    f"${total_revenue:.2f}",
                ]
            )

        self.message_user(request, f"Exported data for {queryset.count()} shops")
        return response

    export_shop_data.short_description = "📊 Export Shop Data"

    def mark_as_active(self, request, queryset):
        """Mark selected shops as active"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request, f"✅ Marked {updated} shops as active", level=messages.SUCCESS
        )

    mark_as_active.short_description = "✅ Mark as Active"

    def mark_as_inactive(self, request, queryset):
        """Mark selected shops as inactive"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request, f"❌ Marked {updated} shops as inactive", level=messages.SUCCESS
        )

    mark_as_inactive.short_description = "❌ Mark as Inactive"

    def check_and_suspend_trial_completed_shops(self, request, queryset):
        """
        Admin action to check and suspend shops that should be suspended
        but were accidentally left active after trial completion
        """
        from apps.billing.models import ShopSubscription
        from django.utils import timezone

        # Find shops that should be suspended
        shops_to_suspend = []

        for shop in queryset:
            try:
                # Get shop subscription
                subscription = ShopSubscription.objects.filter(shop=shop).first()

                if not subscription:
                    self.message_user(
                        request,
                        f"⚠️ {shop.shop_domain}: No subscription found",
                        level=messages.WARNING,
                    )
                    continue

                # Check if shop should be suspended based on subscription status
                should_suspend = False
                suspension_reason = None

                if subscription.status == "TRIAL_COMPLETED" and shop.is_active:
                    should_suspend = True
                    suspension_reason = "trial_completed_subscription_required"
                elif subscription.status == "PENDING_APPROVAL" and shop.is_active:
                    should_suspend = True
                    suspension_reason = "subscription_pending_approval"
                elif (
                    subscription.status in ["SUSPENDED", "CANCELLED"] and shop.is_active
                ):
                    should_suspend = True
                    suspension_reason = f"subscription_{subscription.status.lower()}"

                if should_suspend:
                    # Suspend the shop
                    shop.is_active = False
                    shop.suspended_at = timezone.now()
                    shop.suspension_reason = suspension_reason
                    shop.service_impact = "suspended"
                    shop.updated_at = timezone.now()
                    shop.save()

                    shops_to_suspend.append(
                        {
                            "shop": shop,
                            "reason": suspension_reason,
                            "subscription_status": subscription.status,
                        }
                    )

                    self.message_user(
                        request,
                        f"🛑 {shop.shop_domain}: Suspended (Status: {subscription.status})",
                        level=messages.SUCCESS,
                    )
                else:
                    self.message_user(
                        request,
                        f"✅ {shop.shop_domain}: No action needed (Status: {subscription.status}, Active: {shop.is_active})",
                        level=messages.INFO,
                    )

            except Exception as e:
                self.message_user(
                    request,
                    f"❌ {shop.shop_domain}: Error - {str(e)}",
                    level=messages.ERROR,
                )

        # Summary message
        if shops_to_suspend:
            self.message_user(
                request,
                f"🎯 Suspended {len(shops_to_suspend)} shops that should have been suspended",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "✅ No shops needed suspension",
                level=messages.INFO,
            )

    check_and_suspend_trial_completed_shops.short_description = (
        "🛑 Check & Suspend Trial Completed Shops"
    )


@admin.register(OrderData)
class OrderDataAdmin(admin.ModelAdmin):
    list_display = [
        "order_id",
        "shop",
        "order_date",
        "total_amount",
        "order_status",
        "has_attribution",
        "attribution_status",
        "attribution_revenue",
    ]
    list_filter = [
        "shop",
        "order_date",
        "order_status",
    ]
    search_fields = ["order_id", "shop__shop_domain", "customer_email"]
    date_hierarchy = "order_date"
    actions = [
        "recalculate_attribution",
        "trigger_order_data_collection",
        "export_orders_data",
        "mark_as_paid",
        "mark_as_fulfilled",
    ]
    readonly_fields = [
        "order_id",
        "shop",
        "order_date",
        "total_amount",
        "has_attribution",
        "attribution_revenue",
    ]
    fieldsets = (
        (
            "Order Information",
            {
                "fields": (
                    "order_id",
                    "shop",
                    "order_date",
                    "total_amount",
                    "order_status",
                )
            },
        ),
        (
            "Customer",
            {"fields": ("customer_email", "customer_name"), "classes": ("collapse",)},
        ),
        (
            "Attribution",
            {
                "fields": ("has_attribution", "attribution_revenue"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_attribution(self, obj):
        return obj.shop.purchase_attributions.filter(order_id=obj.order_id).exists()

    has_attribution.boolean = True
    has_attribution.short_description = "Has Attribution"

    def attribution_status(self, obj):
        if self.has_attribution(obj):
            return "✅ Attributed"
        else:
            return "⚠️ Missing"

    attribution_status.short_description = "Status"

    def attribution_revenue(self, obj):
        """Show attributed revenue for this order"""
        try:
            attribution = obj.shop.purchase_attributions.filter(
                order_id=obj.order_id
            ).first()
            if attribution:
                return f"${attribution.attributed_revenue:.2f}"
            return "$0.00"
        except:
            return "N/A"

    attribution_revenue.short_description = "Attributed Revenue"

    def attribution_status_filter(self, obj):
        """Filter method for attribution status"""
        return "attributed" if self.has_attribution(obj) else "missing"

    def get_queryset(self, request):
        """Override to handle JSON fields properly"""
        try:
            return super().get_queryset(request).select_related("shop")
        except Exception as e:
            # Log the error and return a basic queryset
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in OrderDataAdmin.get_queryset: {e}")
            return OrderData.objects.none()

    def changelist_view(self, request, extra_context=None):
        """Override to handle JSON field errors gracefully"""
        try:
            return super().changelist_view(request, extra_context)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in OrderDataAdmin.changelist_view: {e}")
            from django.contrib import messages

            messages.error(request, f"Error loading orders: {str(e)}")
            # Return a simple error page instead of crashing
            from django.shortcuts import render

            return render(
                request,
                "admin/error.html",
                {"error": str(e), "title": "Error loading orders"},
            )

    def recalculate_attribution(self, request, queryset):
        """Admin action to recalculate attribution for selected orders"""
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_API_URL", "http://localhost:8000"
        )

        success_count = 0
        for order in queryset:
            try:
                response = requests.post(
                    f"{python_worker_url}/api/v1/attribution/retrigger",
                    json={
                        "shop_id": str(order.shop.id),
                        "order_id": order.order_id,
                        "dry_run": False,
                    },
                    timeout=60,
                )

                if response.status_code == 200:
                    success_count += 1

            except Exception as e:
                messages.error(
                    request, f"Failed to recalculate order {order.order_id}: {str(e)}"
                )

        if success_count > 0:
            messages.success(
                request,
                f"Successfully recalculated attribution for {success_count} orders.",
            )
        else:
            messages.error(request, "No orders were processed successfully.")

    recalculate_attribution.short_description = "🔄 Recalculate Attribution"

    def trigger_order_data_collection(self, request, queryset):
        """Trigger data collection for selected orders"""
        python_worker_url = getattr(
            settings, "PYTHON_WORKER_API_URL", "http://localhost:8001"
        )
        success_count = 0
        total_orders = queryset.count()

        # Group orders by shop for efficient processing
        shops = {}
        for order in queryset:
            shop_id = str(order.shop.id)
            if shop_id not in shops:
                shops[shop_id] = {"shop": order.shop, "orders": []}
            shops[shop_id]["orders"].append(order.order_id)

        for shop_id, shop_data in shops.items():
            try:
                response = requests.post(
                    f"{python_worker_url}/api/v1/data-collection/trigger",
                    json={
                        "shop_id": shop_id,
                        "data_types": ["orders"],  # Only collect orders for this action
                        "since_hours": 24,
                        "force_refresh": True,
                        "dry_run": False,
                    },
                    timeout=300,  # 5 minutes timeout for data collection
                )

                if response.status_code == 200:
                    result = response.json()
                    success_count += len(shop_data["orders"])
                    messages.success(
                        request,
                        f"✅ Data collection triggered for {shop_data['shop'].shop_domain}: "
                        f"{result.get('orders_collected', 0)} orders collected",
                    )
                else:
                    messages.error(
                        request,
                        f"❌ Failed to trigger data collection for {shop_data['shop'].shop_domain}: "
                        f"{response.status_code}",
                    )

            except Exception as e:
                messages.error(
                    request,
                    f"❌ Error triggering data collection for {shop_data['shop'].shop_domain}: {str(e)}",
                )

        if success_count > 0:
            messages.success(
                request,
                f"🚀 Data collection triggered for {success_count} orders across {len(shops)} shops",
            )
        else:
            messages.error(request, "No data collection was triggered successfully.")

    trigger_order_data_collection.short_description = "📥 Trigger Order Data Collection"

    def export_orders_data(self, request, queryset):
        """Export orders data to CSV"""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders_data.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Order ID",
                "Shop Domain",
                "Date",
                "Amount",
                "Status",
                "Has Attribution",
                "Attributed Revenue",
                "Customer Email",
            ]
        )

        for order in queryset:
            has_attr = self.has_attribution(order)
            attr_revenue = self.attribution_revenue(order)

            writer.writerow(
                [
                    order.order_id,
                    order.shop.shop_domain,
                    order.order_date.strftime("%Y-%m-%d"),
                    f"${order.total_amount:.2f}",
                    order.order_status or "Unknown",
                    "Yes" if has_attr else "No",
                    attr_revenue,
                    getattr(order, "customer_email", "N/A"),
                ]
            )

        self.message_user(request, f"Exported data for {queryset.count()} orders")
        return response

    export_orders_data.short_description = "📊 Export Orders Data"

    def mark_as_paid(self, request, queryset):
        """Mark selected orders as paid"""
        updated = queryset.update(order_status="PAID")
        self.message_user(
            request, f"✅ Marked {updated} orders as paid", level=messages.SUCCESS
        )

    mark_as_paid.short_description = "💰 Mark as Paid"

    def mark_as_fulfilled(self, request, queryset):
        """Mark selected orders as fulfilled"""
        updated = queryset.update(order_status="FULFILLED")
        self.message_user(
            request, f"✅ Marked {updated} orders as fulfilled", level=messages.SUCCESS
        )

    mark_as_fulfilled.short_description = "📦 Mark as Fulfilled"
