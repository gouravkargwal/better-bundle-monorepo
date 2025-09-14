import { Grid, Style } from "@shopify/ui-extensions-react/customer-account";
import { ProductCard } from "./ProductCard";

interface Product {
  id: string;
  title: string;
  handle: string;
  price: string;
  image: string;
  inStock: boolean;
  url: string;
  variant_id?: string;
}

interface ProductGridProps {
  products: Product[];
  onShopNow: (productId: string, position: number, productUrl: string) => void;
  columns?: {
    extraSmall?: number;
    small?: number;
    medium?: number;
    large?: number;
  };
}

export function ProductGrid({
  products,
  onShopNow,
  columns = {
    extraSmall: 1,
    small: 2,
    medium: 3,
    large: 4,
  },
}: ProductGridProps) {
  // Create column arrays based on props
  const getColumnsArray = (count: number) => Array(count).fill("fill");

  const columnsConfig = Style.default(getColumnsArray(columns.extraSmall || 1))
    .when(
      { viewportInlineSize: { min: "extraSmall" } },
      getColumnsArray(columns.extraSmall || 1),
    )
    .when(
      { viewportInlineSize: { min: "small" } },
      getColumnsArray(columns.small || 2),
    )
    .when(
      { viewportInlineSize: { min: "medium" } },
      getColumnsArray(columns.medium || 3),
    )
    .when(
      { viewportInlineSize: { min: "large" } },
      getColumnsArray(columns.large || 4),
    );

  // Filter products based on maxProducts limit (this would need to be handled at the parent level)
  // For now, we'll show all products but the parent can limit them
  const displayProducts = products;

  return (
    <Grid columns={columnsConfig} spacing="base">
      {displayProducts.map((product, index) => (
        <ProductCard
          key={product.id}
          product={product}
          position={index + 1}
          onShopNow={onShopNow}
        />
      ))}
    </Grid>
  );
}
