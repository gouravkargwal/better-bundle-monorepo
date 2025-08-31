// Core application types
export type AnalysisState =
  | "idle"
  | "loading"
  | "success"
  | "error"
  | "no-data"
  | "checking";
export type AnalysisError =
  | "no-orders"
  | "insufficient-data"
  | "api-error"
  | "timeout"
  | "no-products"
  | "no-data";
export type BundleStrength = "Strong" | "Medium" | "Weak";

// Bundle analysis types
export interface BundleAnalysisConfig {
  minSupport: number;
  minConfidence: number;
  minLift: number;
  maxBundleSize: number;
  analysisWindow: number;
  minRevenue: number;
  minUniqueCustomers: number;
  minAvgOrderValue: number;
  minBundleFrequency: number;
  maxBundlePrice: number;
  minBundlePrice: number;
  categoryCompatibility: boolean;
  inventoryCheck: boolean;
  excludeOutOfStock: boolean;
  seasonalFiltering: boolean;
  customerSegmentFiltering: boolean;
  marginThreshold: number;
  bundleComplexity: "simple" | "moderate" | "complex";
}

export interface Bundle {
  id: string;
  productIds: string[];
  products?: Array<{
    id: string;
    title: string;
    price: number;
    imageUrl?: string;
  }>;
  coPurchaseCount: number;
  confidence: number;
  lift: number;
  support: number;
  revenue: number;
  avgOrderValue: number;
  strength: BundleStrength;
  strengthColor: string;
}

export interface AnalysisResults {
  bundles: Bundle[];
  summary: {
    totalBundles: number;
    totalRevenue: number;
    avgConfidence: number;
    avgLift: number;
    avgBundleValue: number;
  };
  metadata: {
    ordersAnalyzed: number;
    productsAnalyzed: number;
    analysisDate: string;
  };
}

// Data validation types
export interface DataValidationResult {
  isValid: boolean;
  orderCount: number;
  productCount: number;
  error?: string;
  errorType?: AnalysisError;
  recommendations?: string[];
}

// Order and product types
export interface OrderLineItem {
  productId: string;
  variantId?: string;
  quantity: number;
  price: number;
  product?: {
    id: string;
    title?: string;
    category?: string;
  };
  variant?: {
    id: string;
    price: string;
    product?: {
      id: string;
    };
  };
}

export interface ProcessedOrder {
  orderId: string;
  customerId?: string;
  totalAmount: number;
  orderDate: Date;
  lineItems: OrderLineItem[];
}

// Store types
export interface StoreStats {
  orderCount: number;
  productCount: number;
  lastAnalysisDate?: Date;
  hasAnalysis: boolean;
}

// API response types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  errorType?: AnalysisError;
  recommendations?: string[];
}

// UI component types
export interface ErrorState {
  title: string;
  description: string;
  action: {
    content: string;
    onAction: () => void;
  };
  recommendations?: string[];
}
