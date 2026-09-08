// features/overview/types/overview.types.ts
import type { ImpactDashboardData } from "../../impact/types/impact.types";

export type SurfaceKey =
  | "mercury"
  | "apollo"
  | "thank_you"
  | "phoenix"
  | "venus";

export type SurfaceLiveStatus = "live" | "no_traffic" | "disabled";

export interface SurfaceStatus {
  key: SurfaceKey;
  label: string;
  emoji: string;
  enabled: boolean;
  impressions: number;
  accepts: number;
  revenue: number;
  status: SurfaceLiveStatus;
}

export interface TopProduct {
  productId: string;
  title: string;
  imageUrl: string | null;
  price: number | null;
  accepts: number;
  revenue: number;
}

export interface EdgeStatus {
  /** Worker responded to the status call */
  reachable: boolean;
  servable: boolean;
  products: number;
  totalEdges: number;
  observedEdges: number;
}

export interface OverviewData {
  impact: ImpactDashboardData;
  edges: EdgeStatus;
  surfaces: SurfaceStatus[];
  topProducts: TopProduct[];
  shopCurrency: string;
}