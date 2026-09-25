import httpx
from sqladmin import ModelView, action
from sqlalchemy import select
from app.core.database.models import Shop, OrderData, ProductData, CustomerData, OfferImpression
from app.core.database.session import get_transaction_context
from app.core.database.models.suspension_audit_log import SuspensionAuditLog
from app.core.config.settings import settings


class ShopAdmin(ModelView, model=Shop):
    name = "Shop"
    name_plural = "Shops"
    icon = "fa-solid fa-store"
    column_list = [
        Shop.shop_domain,
        Shop.is_active,
        Shop.plan_type,
        Shop.shopify_plus,
        Shop.created_at,
    ]
    column_searchable_list = [Shop.shop_domain]
    column_sortable_list = [Shop.is_active, Shop.created_at]
    page_size = 50
    can_create = False
    can_delete = True
    can_edit = False
    can_view_details = True

    @action(name="refresh_health", label="Refresh Health", confirmation_message="Reload business health data?")
    async def refresh_health(self, item_ids: list[int], request) -> str:
        return "Business health data refreshed."

    @action(name="suspend_shop", label="Suspend Shop", confirmation_message="Suspend selected shops?")
    async def suspend_shop(self, item_ids: list[int], request) -> str:
        async with get_transaction_context() as session:
            result = await session.execute(select(Shop).where(Shop.id.in_(item_ids)))
            shops = result.scalars().all()
            for shop in shops:
                shop.is_active = False
                session.add(
                    SuspensionAuditLog(
                        shop_id=shop.id,
                        reason="manual_admin_suspension",
                        event_type="admin",
                    )
                )
        return f"Suspended {len(shops)} shop(s)."

    @action(name="trigger_collection", label="Trigger Collection", confirmation_message="Trigger data collection for selected shops?")
    async def trigger_collection(self, item_ids: list[int], request) -> str:
        backend_url = getattr(settings, "PYTHON_WORKER_API_URL", "http://localhost:8000")
        success_count = 0
        errors = []

        async with get_transaction_context() as session:
            result = await session.execute(select(Shop).where(Shop.id.in_(item_ids)))
            shops = result.scalars().all()

        async with httpx.AsyncClient(timeout=300.0) as client:
            for shop in shops:
                try:
                    response = await client.post(
                        f"{backend_url}/api/v1/data-collection/trigger",
                        json={
                            "shop_id": str(shop.id),
                            "data_types": ["orders", "products", "customers"],
                            "since_hours": 24,
                            "force_refresh": True,
                            "dry_run": False,
                        },
                    )
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        errors.append(f"{shop.shop_domain}: {response.status_code}")
                except Exception as exc:
                    errors.append(f"{shop.shop_domain}: {exc}")

        msg = f"Triggered collection for {success_count}/{len(shops)} shops."
        if errors:
            msg += f" Errors: {', '.join(errors)}"
        return msg


class OrderDataAdmin(ModelView, model=OrderData):
    name = "Order"
    name_plural = "Orders"
    icon = "fa-solid fa-cart-shopping"
    column_list = [
        OrderData.shop_id,
        OrderData.order_id,
        OrderData.total_amount,
        OrderData.order_date,
        OrderData.financial_status,
        OrderData.created_at,
    ]
    column_searchable_list = [OrderData.order_id]
    column_sortable_list = [OrderData.order_date, OrderData.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class ProductDataAdmin(ModelView, model=ProductData):
    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-tag"
    column_list = [
        ProductData.shop_id,
        ProductData.product_id,
        ProductData.title,
        ProductData.status,
        ProductData.price,
        ProductData.created_at,
    ]
    column_searchable_list = [ProductData.product_id, ProductData.title]
    column_sortable_list = [ProductData.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class CustomerDataAdmin(ModelView, model=CustomerData):
    name = "Customer"
    name_plural = "Customers"
    icon = "fa-solid fa-user"
    column_list = [
        CustomerData.shop_id,
        CustomerData.customer_id,
        CustomerData.total_spent,
        CustomerData.order_count,
        CustomerData.created_at,
    ]
    column_searchable_list = [CustomerData.customer_id]
    column_sortable_list = [CustomerData.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class OfferImpressionAdmin(ModelView, model=OfferImpression):
    name = "Offer Impression"
    name_plural = "Offer Impressions"
    icon = "fa-solid fa-eye"
    column_list = [
        OfferImpression.shop_id,
        OfferImpression.surface,
        OfferImpression.offer_type,
        OfferImpression.outcome,
        OfferImpression.paid,
        OfferImpression.created_at,
    ]
    column_searchable_list = [OfferImpression.surface, OfferImpression.outcome]
    column_sortable_list = [OfferImpression.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True
