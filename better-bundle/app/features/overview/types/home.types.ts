// features/overview/types/home.types.ts
import type { ProofResult } from "../../impact/types/proof.types";
import type { CycleMetrics } from "../services/cycle.service";

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

export interface HomeData {
  /** Money for the open billing cycle, from commission_records/billing_cycles. */
  cycle: CycleMetrics;
  /**
   * The incrementality result, as a state rather than a number.
   *
   * Was the whole `ImpactDashboardData`, from which this page rendered
   * `summary.incrementalRevenue` under the label "Revenue Impact — measured
   * against a control group". That figure was attributed revenue, and the
   * "measured" claim beside it was not true. Home now shows one honest line
   * and links to Proof for the detail.
   */
  proof: ProofResult;
  holdoutPercent: number;
  edges: EdgeStatus;
  surfaces: SurfaceStatus[];
  topProducts: TopProduct[];
  shopCurrency: string;
}