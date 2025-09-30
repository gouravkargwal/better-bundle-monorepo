"""
Simple Gorse Feedback Type Mapping
Maps our database feedback types to Gorse feedback types
"""

# =============================================================================
# GORSE FEEDBACK TYPES (What Gorse expects)
# =============================================================================


class GorseFeedbackType:
    """Feedback types that Gorse expects"""

    VIEW = "view"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    PURCHASE = "purchase"
    CLICK = "click"
    CART_VIEW = "cart_view"


# =============================================================================
# MAPPING FUNCTION
# =============================================================================


def map_to_gorse_feedback_type(interaction_type: str) -> str:
    """
    Map our interaction types to Gorse feedback types

    Args:
        interaction_type: Our interaction type (e.g., "add_to_cart")

    Returns:
        str: Gorse feedback type (e.g., "cart_add")
    """
    mapping = {
        # Our interaction types -> Gorse feedback types
        "recommendation_viewed": GorseFeedbackType.VIEW,
        "recommendation_clicked": GorseFeedbackType.CLICK,
        "product_viewed": GorseFeedbackType.VIEW,
        "product_clicked": GorseFeedbackType.CLICK,
        "add_to_cart": GorseFeedbackType.CART_ADD,
        "remove_from_cart": GorseFeedbackType.CART_REMOVE,
        "purchase": GorseFeedbackType.PURCHASE,
        "page_viewed": GorseFeedbackType.VIEW,
        "cart_view": GorseFeedbackType.CART_VIEW,
    }

    return mapping.get(interaction_type, GorseFeedbackType.VIEW)
