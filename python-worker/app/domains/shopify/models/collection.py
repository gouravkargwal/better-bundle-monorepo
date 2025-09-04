"""
Shopify collection model for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class ShopifyCollection(BaseModel):
    """Shopify collection model"""

    # Core collection information
    id: str = Field(..., description="Collection ID")
    title: str = Field(..., description="Collection title")
    handle: str = Field(..., description="Collection handle/URL slug")

    # Collection content
    description: Optional[str] = Field(None, description="Collection description")
    description_html: Optional[str] = Field(
        None, description="Collection description in HTML"
    )

    # Collection metadata
    seo_title: Optional[str] = Field(None, description="SEO title")
    seo_description: Optional[str] = Field(None, description="SEO description")
    meta_description: Optional[str] = Field(None, description="Meta description")

    # Collection settings
    sort_order: str = Field(
        "manual", description="Sort order (manual, best-selling, title, price, etc.)"
    )
    template_suffix: Optional[str] = Field(None, description="Template suffix")

    # Collection status (removed published_at as it doesn't exist in GraphQL)
    published_scope: str = Field("web", description="Publication scope")

    # Collection statistics
    products_count: int = Field(0, description="Number of products in collection")

    # Collection image
    image_id: Optional[str] = Field(None, description="Collection image ID")
    image_url: Optional[str] = Field(None, description="Collection image URL")
    image_alt_text: Optional[str] = Field(None, description="Collection image alt text")

    # Collection products (basic info)
    product_ids: List[str] = Field(
        default_factory=list, description="Product IDs in collection"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=now_utc, description="Collection creation date"
    )
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

    @property
    def is_published(self) -> bool:
        """Check if collection is published (always true for GraphQL collections)"""
        return True  # GraphQL collections are always published

    @property
    def has_description(self) -> bool:
        """Check if collection has a description"""
        return bool(self.description or self.description_html)

    @property
    def has_image(self) -> bool:
        """Check if collection has an image"""
        return bool(self.image_id or self.image_url)

    @property
    def is_automated(self) -> bool:
        """Check if collection is automated (not manual)"""
        return self.sort_order != "manual"

    @property
    def is_manual(self) -> bool:
        """Check if collection is manual"""
        return self.sort_order == "manual"

    @property
    def days_since_creation(self) -> int:
        """Get days since collection creation"""
        return (now_utc() - self.created_at).days

    @property
    def days_since_update(self) -> int:
        """Get days since last update"""
        return (now_utc() - self.updated_at).days

    @property
    def days_since_publication(self) -> Optional[int]:
        """Get days since publication (use creation date for GraphQL collections)"""
        return (now_utc() - self.created_at).days

    @property
    def collection_type(self) -> str:
        """Get collection type based on configuration"""
        if self.is_automated:
            if "best-selling" in self.sort_order:
                return "best_selling"
            elif "title" in self.sort_order:
                return "alphabetical"
            elif "price" in self.sort_order:
                return "price_based"
            elif "created" in self.sort_order:
                return "date_based"
            else:
                return "automated"
        else:
            return "manual"

    @property
    def collection_size_category(self) -> str:
        """Get collection size category"""
        if self.products_count == 0:
            return "empty"
        elif self.products_count <= 10:
            return "small"
        elif self.products_count <= 50:
            return "medium"
        elif self.products_count <= 200:
            return "large"
        else:
            return "very_large"

    @property
    def has_seo_optimization(self) -> bool:
        """Check if collection has SEO optimization"""
        return bool(self.seo_title or self.seo_description or self.meta_description)

    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this collection"""
        return {
            "collection_id": self.id,
            "products_count": self.products_count,
            "days_since_creation": self.days_since_creation,
            "days_since_update": self.days_since_update,
            "days_since_publication": self.days_since_publication,
            "is_published": self.is_published,
            "is_automated": self.is_automated,
            "is_manual": self.is_manual,
            "has_description": self.has_description,
            "has_image": self.has_image,
            "has_seo_optimization": self.has_seo_optimization,
            "collection_type": self.collection_type,
            "collection_size_category": self.collection_size_category,
            "sort_order": self.sort_order,
            "published_scope": self.published_scope,
        }

    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()

        # Update fields from raw data if they exist
        if "collection" in raw_data:
            collection_data = raw_data["collection"]
            for field, value in collection_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)

    def add_product(self, product_id: str) -> None:
        """Add a product to the collection"""
        if product_id not in self.product_ids:
            self.product_ids.append(product_id)
            self.products_count = len(self.product_ids)

    def remove_product(self, product_id: str) -> None:
        """Remove a product from the collection"""
        if product_id in self.product_ids:
            self.product_ids.remove(product_id)
            self.products_count = len(self.product_ids)

    def has_product(self, product_id: str) -> bool:
        """Check if collection contains a product"""
        return product_id in self.product_ids

    def get_product_count(self) -> int:
        """Get number of products in collection"""
        return len(self.product_ids)

    def clear_products(self) -> None:
        """Clear all products from collection"""
        self.product_ids.clear()
        self.products_count = 0

    def set_image(
        self, image_id: str, image_url: str, alt_text: Optional[str] = None
    ) -> None:
        """Set collection image"""
        self.image_id = image_id
        self.image_url = image_url
        self.image_alt_text = alt_text

    def remove_image(self) -> None:
        """Remove collection image"""
        self.image_id = None
        self.image_url = None
        self.image_alt_text = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
