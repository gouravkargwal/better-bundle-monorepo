"""
Views for shops app - Pure Django Admin Approach
All functionality is handled by Django Admin interface
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
import json
from .models import Shop
from apps.billing.models import ShopSubscription


@login_required
@staff_member_required
def admin_dashboard(request):
    """Simple dashboard redirect to Django admin"""
    from django.http import HttpResponseRedirect
    from django.urls import reverse

    return HttpResponseRedirect(reverse("admin:index"))


@staff_member_required
@require_http_methods(["POST"])
def check_and_suspend_shops_api(request):
    """
    API endpoint to check and suspend shops that should be suspended
    but were accidentally left active after trial completion
    """
    try:
        data = json.loads(request.body)
        shop_ids = data.get("shop_ids", [])
        check_all = data.get("check_all", False)

        if check_all:
            # Check all active shops
            shops = Shop.objects.filter(is_active=True)
        elif shop_ids:
            # Check specific shops
            shops = Shop.objects.filter(id__in=shop_ids)
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Either shop_ids or check_all must be provided",
                },
                status=400,
            )

        results = []
        suspended_count = 0

        for shop in shops:
            try:
                # Get shop subscription
                subscription = ShopSubscription.objects.filter(shop=shop).first()

                if not subscription:
                    results.append(
                        {
                            "shop_id": str(shop.id),
                            "shop_domain": shop.shop_domain,
                            "action": "skipped",
                            "reason": "No subscription found",
                            "subscription_status": None,
                        }
                    )
                    continue

                # Check if shop should be suspended
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

                    suspended_count += 1
                    results.append(
                        {
                            "shop_id": str(shop.id),
                            "shop_domain": shop.shop_domain,
                            "action": "suspended",
                            "reason": suspension_reason,
                            "subscription_status": subscription.status,
                            "suspended_at": shop.suspended_at.isoformat(),
                        }
                    )
                else:
                    results.append(
                        {
                            "shop_id": str(shop.id),
                            "shop_domain": shop.shop_domain,
                            "action": "no_action",
                            "reason": "No suspension needed",
                            "subscription_status": subscription.status,
                        }
                    )

            except Exception as e:
                results.append(
                    {
                        "shop_id": str(shop.id),
                        "shop_domain": shop.shop_domain,
                        "action": "error",
                        "reason": str(e),
                        "subscription_status": None,
                    }
                )

        return JsonResponse(
            {
                "success": True,
                "message": f"Processed {len(results)} shops, suspended {suspended_count}",
                "suspended_count": suspended_count,
                "total_processed": len(results),
                "results": results,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@staff_member_required
@require_http_methods(["GET"])
def get_shops_suspension_status(request):
    """
    API endpoint to get shops that should be suspended but are still active
    """
    try:
        # Find shops that should be suspended
        shops_to_check = []

        # Get all active shops with their subscriptions
        active_shops = Shop.objects.filter(is_active=True).select_related()

        for shop in active_shops:
            subscription = ShopSubscription.objects.filter(shop=shop).first()

            if not subscription:
                continue

            should_suspend = False
            suspension_reason = None

            if subscription.status == "TRIAL_COMPLETED":
                should_suspend = True
                suspension_reason = "trial_completed_subscription_required"
            elif subscription.status == "PENDING_APPROVAL":
                should_suspend = True
                suspension_reason = "subscription_pending_approval"
            elif subscription.status in ["SUSPENDED", "CANCELLED"]:
                should_suspend = True
                suspension_reason = f"subscription_{subscription.status.lower()}"

            if should_suspend:
                shops_to_check.append(
                    {
                        "shop_id": str(shop.id),
                        "shop_domain": shop.shop_domain,
                        "subscription_status": subscription.status,
                        "suspension_reason": suspension_reason,
                        "is_active": shop.is_active,
                        "suspended_at": (
                            shop.suspended_at.isoformat() if shop.suspended_at else None
                        ),
                        "suspension_reason_current": shop.suspension_reason,
                    }
                )

        return JsonResponse(
            {
                "success": True,
                "shops_need_suspension": len(shops_to_check),
                "shops": shops_to_check,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
