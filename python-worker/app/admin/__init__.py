from sqladmin import Admin
from app.core.database.engine import create_engine
from .auth import AdminAuth
from app.core.config.settings import settings


def setup_admin(app):
    engine = create_engine()
    auth = AdminAuth(secret_key=settings.ADMIN_SECRET_KEY)
    admin = Admin(
        app,
        engine,
        base_url="/ops",
        title="BetterBundle Ops",
        authentication_backend=auth,
    )

    from app.admin.views.shops import (
        ShopAdmin,
        OrderDataAdmin,
        ProductDataAdmin,
        CustomerDataAdmin,
        OfferImpressionAdmin,
    )
    from app.admin.views.billing import (
        BillingCycleAdmin,
        BillingInvoiceAdmin,
        CommissionRecordAdmin,
        SubscriptionPlanAdmin,
        ShopSubscriptionAdmin,
    )
    from app.admin.views.revenue import PurchaseAttributionAdmin
    from app.admin.views.engine import ProductEdgeAdmin, ProductEnrichmentAdmin
    from app.admin.custom.business_health import BusinessHealthView

    admin.add_view(ShopAdmin)
    admin.add_view(OrderDataAdmin)
    admin.add_view(ProductDataAdmin)
    admin.add_view(CustomerDataAdmin)
    admin.add_view(OfferImpressionAdmin)
    admin.add_view(BillingCycleAdmin)
    admin.add_view(BillingInvoiceAdmin)
    admin.add_view(CommissionRecordAdmin)
    admin.add_view(SubscriptionPlanAdmin)
    admin.add_view(ShopSubscriptionAdmin)
    admin.add_view(PurchaseAttributionAdmin)
    admin.add_view(ProductEdgeAdmin)
    admin.add_view(ProductEnrichmentAdmin)
    admin.add_view(BusinessHealthView)

    return admin
