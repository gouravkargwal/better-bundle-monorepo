// features/overview/services/overview.types.ts
export interface ShopInfo {
  id: string;
  shop_domain: string;
  currency_code: string;
  plan_type: string;
  created_at: Date;
}

export interface BillingPlan {
  id: string;
  name: string;
  type: string;
  status: string;
  configuration: any;
  effective_from: Date;
  effective_to: Date;
}

export interface OverviewMetrics {
  totalRevenue: number;
  currency: string;
  conversionRate: number;
  revenueChange: number | null;
  conversionRateChange: number | null;
  // Additional metrics
  totalOrders: number;
  attributedOrders: number;
  activePlan: {
    name: string;
    type: string;
    description?: string;
    commissionRate: number;
    thresholdAmount: number;
    currency: string;
    status: string;
    startDate: Date;
    isActive: boolean;
  } | null;
}

export interface OverviewData {
  shop: ShopInfo;
  billingPlan: BillingPlan | null;
  overviewData: OverviewMetrics;
}

export interface OverviewError {
  error: string;
}
