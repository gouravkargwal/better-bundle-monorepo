from sqladmin import ModelView
from app.core.database.models import (
    BillingCycle,
    BillingInvoice,
    CommissionRecord,
    SubscriptionPlan,
    ShopSubscription,
)


class BillingCycleAdmin(ModelView, model=BillingCycle):
    name = "Billing Cycle"
    name_plural = "Billing Cycles"
    icon = "fa-solid fa-calendar-days"
    column_list = [
        BillingCycle.shop_subscription_id,
        BillingCycle.cycle_number,
        BillingCycle.start_date,
        BillingCycle.end_date,
        BillingCycle.status,
        BillingCycle.created_at,
    ]
    column_sortable_list = [BillingCycle.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class BillingInvoiceAdmin(ModelView, model=BillingInvoice):
    name = "Billing Invoice"
    name_plural = "Billing Invoices"
    icon = "fa-solid fa-file-invoice"
    column_list = [
        BillingInvoice.shop_subscription_id,
        BillingInvoice.shopify_invoice_id,
        BillingInvoice.total_amount,
        BillingInvoice.status,
        BillingInvoice.invoice_date,
        BillingInvoice.created_at,
    ]
    column_searchable_list = [BillingInvoice.shopify_invoice_id]
    column_sortable_list = [BillingInvoice.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class CommissionRecordAdmin(ModelView, model=CommissionRecord):
    name = "Commission Record"
    name_plural = "Commission Records"
    icon = "fa-solid fa-money-bill"
    column_list = [
        CommissionRecord.shop_id,
        CommissionRecord.order_id,
        CommissionRecord.commission_earned,
        CommissionRecord.commission_charged,
        CommissionRecord.billing_phase,
        CommissionRecord.status,
        CommissionRecord.created_at,
    ]
    column_sortable_list = [CommissionRecord.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class SubscriptionPlanAdmin(ModelView, model=SubscriptionPlan):
    name = "Subscription Plan"
    name_plural = "Subscription Plans"
    icon = "fa-solid fa-list-check"
    column_list = [
        SubscriptionPlan.name,
        SubscriptionPlan.plan_type,
        SubscriptionPlan.commission_rate,
        SubscriptionPlan.cap_amount,
        SubscriptionPlan.is_active,
        SubscriptionPlan.created_at,
    ]
    column_sortable_list = [SubscriptionPlan.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True


class ShopSubscriptionAdmin(ModelView, model=ShopSubscription):
    name = "Shop Subscription"
    name_plural = "Shop Subscriptions"
    icon = "fa-solid fa-repeat"
    column_list = [
        ShopSubscription.shop_id,
        ShopSubscription.subscription_plan_id,
        ShopSubscription.status,
        ShopSubscription.created_at,
    ]
    column_sortable_list = [ShopSubscription.created_at]
    page_size = 50
    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True
