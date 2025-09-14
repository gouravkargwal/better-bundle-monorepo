import { useState, useEffect } from "react";

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

interface UseResponsiveProductsProps {
  products: Product[];
  maxProducts?: {
    extraSmall?: number;
    small?: number;
    medium?: number;
    large?: number;
  };
}

export function useResponsiveProducts({
  products,
  maxProducts = {
    extraSmall: 1,
    small: 2,
    medium: 3,
    large: 4,
  },
}: UseResponsiveProductsProps) {
  const [displayProducts, setDisplayProducts] = useState<Product[]>(products);

  useEffect(() => {
    // This is a simplified approach - in a real app you'd use actual viewport detection
    // For now, we'll use the largest limit as default
    const limit = maxProducts.large || 4;
    setDisplayProducts(products.slice(0, limit));
  }, [products, maxProducts]);

  return displayProducts;
}
