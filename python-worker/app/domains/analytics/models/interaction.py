from enum import Enum


class InteractionType(str, Enum):
    """Types of user interactions"""

    PAGE_VIEWED = "page_viewed"
    PRODUCT_VIEWED = "product_viewed"
    PRODUCT_ADDED_TO_CART = "product_added_to_cart"
    PRODUCT_REMOVED_FROM_CART = "product_removed_from_cart"
    CART_VIEWED = "cart_viewed"
    COLLECTION_VIEWED = "collection_viewed"
    SEARCH_SUBMITTED = "search_submitted"
    CHECKOUT_STARTED = "checkout_started"
    CHECKOUT_COMPLETED = "checkout_completed"
    CUSTOMER_LINKED = "customer_linked"

    RECOMMENDATION_VIEWED = "recommendation_viewed"
    RECOMMENDATION_CLICKED = "recommendation_clicked"
    RECOMMENDATION_ADD_TO_CART = "recommendation_add_to_cart"

    RECOMMENDATION_READY = "recommendation_ready"
    RECOMMENDATION_DECLINED = "recommendation_declined"
