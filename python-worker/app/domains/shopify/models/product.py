"""
Shopify Product model for BetterBundle Python Worker
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

from app.shared.helpers import now_utc


class ShopifyProductVariant(BaseModel):
    """Shopify product variant model"""

    id: str = Field(..., description="Variant ID")
    product_id: str = Field(..., description="Parent product ID")
    title: str = Field(..., description="Variant title")
    sku: Optional[str] = Field(None, description="SKU")
    barcode: Optional[str] = Field(None, description="Barcode")

    # Pricing
    price: float = Field(..., description="Variant price")
    compare_at_price: Optional[float] = Field(None, description="Compare at price")
    cost_per_item: Optional[float] = Field(None, description="Cost per item")

    # Inventory
    inventory_quantity: int = Field(0, description="Inventory quantity")
    inventory_policy: str = Field("deny", description="Inventory policy")
    inventory_management: Optional[str] = Field(
        None, description="Inventory management system"
    )

    # Physical attributes
    weight: Optional[float] = Field(None, description="Weight in grams")
    weight_unit: str = Field("g", description="Weight unit")
    requires_shipping: bool = Field(True, description="Requires shipping")
    taxable: bool = Field(True, description="Is taxable")

    # Options
    option1: Optional[str] = Field(None, description="Option 1 value")
    option2: Optional[str] = Field(None, description="Option 2 value")
    option3: Optional[str] = Field(None, description="Option 3 value")

    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="Creation date")
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )

    # Raw data
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="Raw Shopify API response"
    )

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    @property
    def has_discount(self) -> bool:
        """Check if variant has discount"""
        return self.compare_at_price is not None and self.compare_at_price > self.price

    @property
    def discount_percentage(self) -> Optional[float]:
        """Get discount percentage"""
        if not self.has_discount:
            return None
        return ((self.compare_at_price - self.price) / self.compare_at_price) * 100

    @property
    def profit_margin(self) -> Optional[float]:
        """Get profit margin percentage"""
        if self.cost_per_item is None or self.price <= 0:
            return None
        return ((self.price - self.cost_per_item) / self.price) * 100

    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this variant"""
        return {
            "variant_id": self.id,
            "product_id": self.product_id,
            "price": self.price,
            "compare_at_price": self.compare_at_price or 0,
            "has_discount": self.has_discount,
            "discount_percentage": self.discount_percentage or 0,
            "inventory_quantity": self.inventory_quantity,
            "weight": self.weight or 0,
            "requires_shipping": self.requires_shipping,
            "taxable": self.taxable,
            "profit_margin": self.profit_margin or 0,
            "days_since_creation": self._get_days_since_creation(),
        }

    def _get_days_since_creation(self) -> int:
        """Get days since variant creation"""
        if not self.created_at:
            return 0
        return (now_utc() - self.created_at).days


class ShopifyProduct(BaseModel):
    """Shopify product model"""

    # Core product information
    id: str = Field(..., description="Product ID")
    title: str = Field(..., description="Product title")
    body_html: Optional[str] = Field(None, description="Product description HTML")
    vendor: str = Field(..., description="Product vendor")
    product_type: str = Field(..., description="Product type")

    # SEO and marketing
    handle: str = Field(..., description="Product handle/URL slug")
    seo_title: Optional[str] = Field(None, description="SEO title")
    seo_description: Optional[str] = Field(None, description="SEO description")
    meta_description: Optional[str] = Field(None, description="Meta description")

    # Status and visibility
    status: str = Field("active", description="Product status")
    published_at: Optional[datetime] = Field(None, description="Publication date")
    published_scope: str = Field("web", description="Publication scope")

    # Organization
    tags: List[str] = Field(default_factory=list, description="Product tags")
    template_suffix: Optional[str] = Field(None, description="Template suffix")

    # Images
    image_ids: List[str] = Field(default_factory=list, description="Image IDs")
    main_image_url: Optional[str] = Field(None, description="Main image URL")

    # Collections
    collection_ids: List[str] = Field(
        default_factory=list, description="Collection IDs"
    )

    # Variants
    variants: List[ShopifyProductVariant] = Field(
        default_factory=list, description="Product variants"
    )

    # Options
    options: List[Dict[str, Any]] = Field(
        default_factory=list, description="Product options"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="Creation date")
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )

    # BetterBundle specific fields
    bb_last_sync: Optional[datetime] = Field(None, description="Last BetterBundle sync")
    bb_ml_features_computed: bool = Field(False, description="ML features computed")

    # Raw data storage
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="Raw Shopify API response"
    )

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    @validator("status")
    def validate_status(cls, v):
        """Validate product status"""
        valid_statuses = ["active", "archived", "draft"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        return v

    @property
    def is_published(self) -> bool:
        """Check if product is published"""
        return self.status == "active" and self.published_at is not None

    @property
    def variant_count(self) -> int:
        """Get number of variants"""
        return len(self.variants)

    @property
    def has_multiple_variants(self) -> bool:
        """Check if product has multiple variants"""
        return self.variant_count > 1

    @property
    def price_range(self) -> Dict[str, float]:
        """Get price range across variants"""
        if not self.variants:
            return {"min": 0, "max": 0, "avg": 0}

        prices = [v.price for v in self.variants if v.price > 0]
        if not prices:
            return {"min": 0, "max": 0, "avg": 0}

        return {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
        }

    @property
    def total_inventory(self) -> int:
        """Get total inventory across all variants"""
        return sum(v.inventory_quantity for v in self.variants)

    @property
    def has_images(self) -> bool:
        """Check if product has images"""
        return len(self.image_ids) > 0 or self.main_image_url is not None

    @property
    def image_count(self) -> int:
        """Get number of images"""
        return len(self.image_ids)

    @property
    def tag_count(self) -> int:
        """Get number of tags"""
        return len(self.tags)

    @property
    def collection_count(self) -> int:
        """Get number of collections"""
        return len(self.collection_ids)

    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this product"""
        price_range = self.price_range

        return {
            "product_id": self.id,
            "vendor": self.vendor,
            "product_type": self.product_type,
            "status": self.status,
            "is_published": self.is_published,
            "variant_count": self.variant_count,
            "has_multiple_variants": self.has_multiple_variants,
            "price_min": price_range["min"],
            "price_max": price_range["max"],
            "price_avg": price_range["avg"],
            "price_range": price_range["max"] - price_range["min"],
            "total_inventory": self.total_inventory,
            "has_images": self.has_images,
            "image_count": self.image_count,
            "tag_count": self.tag_count,
            "collection_count": self.collection_count,
            "days_since_creation": self._get_days_since_creation(),
            "days_since_update": self._get_days_since_update(),
            "days_since_publication": self._get_days_since_publication(),
        }

    def _get_days_since_creation(self) -> int:
        """Get days since product creation"""
        if not self.created_at:
            return 0
        return (now_utc() - self.created_at).days

    def _get_days_since_update(self) -> int:
        """Get days since last update"""
        if not self.updated_at:
            return 0
        return (now_utc() - self.updated_at).days

    def _get_days_since_publication(self) -> Optional[int]:
        """Get days since publication"""
        if not self.published_at:
            return None
        return (now_utc() - self.published_at).days

    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()

        # Update fields from raw data if they exist
        if "product" in raw_data:
            product_data = raw_data["product"]
            for field, value in product_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)

    def add_variant(self, variant: ShopifyProductVariant) -> None:
        """Add a variant to the product"""
        self.variants.append(variant)

    def get_variant_by_id(self, variant_id: str) -> Optional[ShopifyProductVariant]:
        """Get variant by ID"""
        for variant in self.variants:
            if variant.id == variant_id:
                return variant
        return None

    def get_variants_by_option(
        self, option_name: str, option_value: str
    ) -> List[ShopifyProductVariant]:
        """Get variants by option value"""
        matching_variants = []
        for variant in self.variants:
            if (
                hasattr(variant, f"option{option_name}")
                and getattr(variant, f"option{option_name}") == option_value
            ):
                matching_variants.append(variant)
        return matching_variants
