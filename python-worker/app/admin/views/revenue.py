from sqladmin import ModelView
from app.core.database.models import PurchaseAttribution


class PurchaseAttributionAdmin(ModelView, model=PurchaseAttribution):
    name = "Purchase Attribution"
    name_plural = "Purchase Attributions"
    icon = "fa-solid fa-link"
    column_list = [
        PurchaseAttribution.shop_id,
        PurchaseAttribution.order_id,
        PurchaseAttribution.total_revenue,
        PurchaseAttribution.attribution_algorithm,
        PurchaseAttribution.purchase_at,
        PurchaseAttribution.created_at,
    ]
    column_searchable_list = [PurchaseAttribution.order_id]
    column_sortable_list = [PurchaseAttribution.purchase_at, PurchaseAttribution.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True
