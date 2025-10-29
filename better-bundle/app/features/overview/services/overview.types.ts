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

export interface PerformanceData {
  topBundles: Array<{
    id: string;
    name: string;
    revenue: number;
    orders: number;
    conversionRate: number;
  }>;
  revenueByExtension: Array<{
    type: string;
    revenue: number;
    percentage: number;
  }>;
  trends: {
    weeklyGrowth: number;
    monthlyGrowth: number;
  };
}

export interface OverviewData {
  shop: ShopInfo;
  billingPlan: BillingPlan | null;
  overviewData: OverviewMetrics;
  performanceData: PerformanceData;
}

export interface OverviewError {
  error: string;
}
