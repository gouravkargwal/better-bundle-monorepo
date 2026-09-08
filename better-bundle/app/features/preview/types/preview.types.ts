// features/preview/types/preview.types.ts

export interface PreviewProduct {
  productId: string;
  title: string;
  imageUrl: string | null;
}

export interface PreviewCandidate {
  product_id: string;
  edge_type: string;
  blended_score: number;
  observed_count: number;
  title: string;
  price: number;
  product_type: string | null;
  source: "observed" | "prior";
}

export interface PreviewResult {
  count: number;
  items: PreviewCandidate[];
  surface: string;
}

export interface PreviewError {
  error: string;
}