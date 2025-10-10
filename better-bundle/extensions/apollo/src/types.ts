interface ProductRecommendationAPI {
  id: string;
  title: string;
  handle: string;
  url: string;
  price: {
    amount: string;
    currency_code: string;
  };
  image: {
    url: string;
    alt_text?: string;
  } | null;
  vendor: string;
  product_type: string;
  available: boolean;
  score: number;
  variant_id: string;
  selectedVariantId: string;
  variants: ProductVariant[];
  options: VariantOption[];
  inventory: number;
  description?: string;
  compare_at_price?: number;
}
interface VariantOption {
  id: string;
  name: string;
  position: number;
  values: string[];
}

interface ProductVariant {
  variant_id: string;
  title: string;
  price: number;
  compare_at_price: number | null;
  sku: string;
  barcode: string | null;
  inventory: number;
  currency_code: string;
}

interface StorageData {
  recommendations: ProductRecommendationAPI[];
  sessionId: string;
  orderId: string;
  customerId: string;
  shopDomain: string;
  purchasedProducts: any[];
  source: string;
  timestamp: number;
  shop: any;
  locale: string;
  initialPurchase: any;
}

interface VariantSelectorProps {
  product: ProductRecommendationAPI;
  selectedVariantId: string;
  onVariantChange: (variantId: string) => void;
  disabled?: boolean;
}

interface ProductCardProps {
  product: ProductRecommendationAPI;
  position: number;
  isAdded: boolean;
  isLoading: boolean;
  onAddToOrder: (
    product: ProductRecommendationAPI,
    variantId: string,
    position: number,
  ) => void;
  variantManagement: UseVariantManagementReturn;
}

interface UseVariantManagementReturn {
  getVariantById: (
    product: ProductRecommendationAPI,
    variantId: string,
  ) => ProductVariant | null;
  isVariantAvailable: (variant: ProductVariant | null) => boolean;
  getSelectedOptions: (variant: ProductVariant) => Record<string, string>;
}

export type {
  ProductRecommendationAPI,
  VariantOption,
  ProductVariant,
  StorageData,
  VariantSelectorProps,
  ProductCardProps,
  UseVariantManagementReturn,
};
