export interface DashboardOverview {
  total_revenue: number;
  conversion_rate: number;
  total_recommendations: number;
  total_clicks: number;
  average_order_value: number;
  period: string;
  currency_code: string;
  money_format: string;
  revenue_change: number | null;
  conversion_rate_change: number | null;
  recommendations_change: number | null;
  clicks_change: number | null;
  aov_change: number | null;
  total_customers: number;
  customers_change: number | null;
}

export interface TopProductData {
  product_id: string;
  title: string;
  revenue: number;
  clicks: number;
  conversion_rate: number;
  recommendations_shown: number;
  currency_code: string;
  customers: number;
}

export interface RecentActivityData {
  today: ActivityMetrics;
  yesterday: ActivityMetrics;
  this_week: ActivityMetrics;
  currency_code: string;
}

export interface ActivityMetrics {
  recommendations: number;
  clicks: number;
  revenue: number;
  customers: number;
}

export interface AttributedMetrics {
  attributed_revenue: number;
  attributed_refunds: number;
  net_attributed_revenue: number;
  attribution_rate: number;
  refund_rate: number;
  currency_code: string;
}

export interface PerformanceMetrics {
  total_recommendations: number;
  total_clicks: number;
  conversion_rate: number;
  total_customers: number;
  recommendations_change: number | null;
  clicks_change: number | null;
  conversion_rate_change: number | null;
  customers_change: number | null;
}

export interface DashboardData {
  overview: DashboardOverview;
  topProducts: TopProductData[];
  recentActivity: RecentActivityData;
  attributedMetrics: AttributedMetrics;
  performance: PerformanceMetrics;
}
