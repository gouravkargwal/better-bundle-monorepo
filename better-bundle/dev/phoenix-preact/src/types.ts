export type Variant = {
  variant_id: string | number;
  title: string;
  price: number;
  compare_at_price?: number | null;
  available: boolean;
  inventory?: number | null;
  option1?: string | null;
  option2?: string | null;
  option3?: string | null;
  image?: string | null;
};

export type ProductOption = {
  name: string;
  values: string[];
};

export type Product = {
  id: string | number;
  title: string;
  image: string;
  url: string;
  price: number;
  compare_at_price?: number | null;
  currency: string;
  variants: Variant[];
  options?: ProductOption[];
  images?: string[];
};

export type RecommendationContext =
  | "product_page"
  | "cart"
  | "collection_page"
  | "homepage";

export type RecommendationResponse = Product[];
