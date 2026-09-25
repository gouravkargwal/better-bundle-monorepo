from sqladmin import ModelView
from app.core.database.models import ProductEdge, ProductEnrichment


class ProductEdgeAdmin(ModelView, model=ProductEdge):
    name = "Product Edge"
    name_plural = "Product Edges"
    icon = "fa-solid fa-diagram-project"
    column_list = [
        ProductEdge.shop_id,
        ProductEdge.source_product_id,
        ProductEdge.target_product_id,
        ProductEdge.edge_type,
        ProductEdge.blended_score,
        ProductEdge.observed_count,
        ProductEdge.created_at,
    ]
    column_searchable_list = [
        ProductEdge.source_product_id,
        ProductEdge.target_product_id,
        ProductEdge.edge_type,
    ]
    column_sortable_list = [ProductEdge.blended_score, ProductEdge.observed_count]
    page_size = 50
    can_create = False
    can_delete = True
    can_edit = False
    can_view_details = True


class ProductEnrichmentAdmin(ModelView, model=ProductEnrichment):
    name = "Product Enrichment"
    name_plural = "Product Enrichments"
    icon = "fa-solid fa-wand-magic-sparkles"
    column_list = [
        ProductEnrichment.shop_id,
        ProductEnrichment.product_id,
        ProductEnrichment.status,
        ProductEnrichment.attempts,
        ProductEnrichment.model_version,
        ProductEnrichment.created_at,
    ]
    column_searchable_list = [ProductEnrichment.product_id, ProductEnrichment.status]
    column_sortable_list = [ProductEnrichment.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True
