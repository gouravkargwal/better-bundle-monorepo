// Types for the incrementality impact dashboard

export interface ImpactSummary {
  incrementalRevenue: number;
  incrementalRevenueLower: number;  // 95% CI lower
  incrementalRevenueUpper: number;  // 95% CI upper
  aovLiftPercent: number;
  treatmentAov: number;
  controlAov: number;
  treatmentOrders: number;
  controlOrders: number;
  totalImpressions: number;
  totalAccepts: number;
  pValue: number;
  isSignificant: boolean;
  status: 'collecting' | 'significant' | 'sentinel';
}

export interface FunnelRow {
  surface: 'apollo' | 'mercury';
  impressions: number;
  accepts: number;
  revenue: number;
  conversionRate: number;
}

export interface OfferPair {
  productIdA: string;
  productTitleA: string;
  productIdB: string;
  productTitleB: string;
  impressions: number;
  accepts: number;
  revenue: number;
  conversionRate: number;
}

export interface HoldoutConfig {
  enabled: boolean;
  percent: number;
  status: string;
}

export interface TrendPoint {
  /** ISO date (YYYY-MM-DD) */
  date: string;
  impressions: number;
  revenue: number;
}

export type InsightTone = "success" | "info" | "warning" | "critical";

export interface ActionableInsight {
  tone: InsightTone;
  text: string;
}

export interface ImpactDashboardData {
  summary: ImpactSummary;
  funnels: FunnelRow[];
  topOffers: OfferPair[];
  worstOffers: OfferPair[];
  holdoutConfig: HoldoutConfig;
  currencyCode: string;
  /** Daily accepted revenue + impressions over the selected window */
  trends: TrendPoint[];
  /** Computed, merchant-facing suggestions */
  insights: ActionableInsight[];
}
