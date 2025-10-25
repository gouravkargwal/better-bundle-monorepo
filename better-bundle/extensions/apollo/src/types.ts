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
  images?: {
    url: string;
    alt_text?: string;
  }[];
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

interface ProductOption {
  id: string;
  name: string;
  position: number;
  values: string[];
}

interface ProductRecommendation {
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
  options: ProductOption[];
  inventory: number;
  // Optional fields
  compare_at_price?: {
    amount: string;
    currency_code: string;
  };
  description?: string;
  tags?: string[];
  reason?: string;
  // Post-purchase compliance fields
  requires_shipping?: boolean;
  subscription?: boolean;
  selling_plan?: any;
}

interface SessionData {
  session_id: string;
  customer_id: string | null;
  client_id: string | null;
  created_at: string;
  expires_at: string | null;
}

interface CombinedAPIResponse {
  success: boolean;
  message: string;
  session_data: SessionData;
  recommendations: ProductRecommendation[];
  recommendation_count: number;
}

type ExtensionContext =
  | "homepage"
  | "product_page"
  | "collection_page"
  | "cart_page"
  | "search_page"
  | "customer_account"
  | "checkout_page"
  | "order_page"
  | "thank_you_page"
  | "post_purchase";

type InteractionType =
  | "page_viewed"
  | "product_viewed"
  | "product_added_to_cart"
  | "product_removed_from_cart"
  | "cart_viewed"
  | "collection_viewed"
  | "search_submitted"
  | "checkout_started"
  | "checkout_completed"
  | "customer_linked"
  | "recommendation_ready"
  | "recommendation_viewed"
  | "recommendation_clicked"
  | "recommendation_add_to_cart"
  | "recommendation_declined";

interface UnifiedInteractionRequest {
  session_id: string;
  shop_domain: string;
  context: ExtensionContext;
  interaction_type: InteractionType;
  customer_id?: string;
  product_id?: string;
  collection_id?: string;
  search_query?: string;
  page_url?: string;
  referrer?: string;
  metadata: Record<string, any>;
}

interface UnifiedResponse {
  success: boolean;
  message: string;
  data?: {
    session_id?: string;
    interaction_id?: string;
    [key: string]: any;
  };
  // Session recovery information
  session_recovery?: {
    original_session_id: string;
    new_session_id: string;
    recovery_reason: string;
    recovered_at: string;
  };
}

export type {
  ProductRecommendationAPI,
  VariantOption,
  StorageData,
  VariantSelectorProps,
  ProductCardProps,
  UseVariantManagementReturn,
  CombinedAPIResponse,
  ProductRecommendation,
  ProductOption,
  ProductVariant,
  ExtensionContext,
  InteractionType,
  UnifiedInteractionRequest,
  UnifiedResponse,
};
