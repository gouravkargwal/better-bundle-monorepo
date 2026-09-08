import {
  Grid,
  TextBlock,
  Button,
  Image,
  View,
  Card,
  BlockStack,
} from "@shopify/ui-extensions-react/customer-account";
import { useState, useEffect, useRef } from "react";
import { logger } from "../utils/logger";

interface Product {
  id: string;
  title: string;
  handle: string;
  price: string;
  image: {
    url: string;
    alt_text?: string;
  } | null;
  images?: Array<{
    url: string;
    alt_text?: string;
    type?: string;
    position?: number;
  }>;
  inStock: boolean;
  url: string;
  variant_id?: string;
  variants?: Array<{
    id: string;
    title: string;
    price: string;
    available: boolean;
  }>;
}

interface ProductCardProps {
  product: Product;
  position: number;
  onShopNow: (
    productId: string,
    position: number,
    productUrl: string,
  ) => Promise<void>;
}

export function ProductCard({
  product,
  position,
  onShopNow,
}: ProductCardProps) {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Get available images (fallback to main image if no images array)
  const availableImages =
    product.images && product.images.length > 0
      ? product.images
      : product.image
        ? [product.image]
        : [];

  const currentImage = availableImages[currentImageIndex];

  // Clean auto-slide functionality
  useEffect(() => {
    if (availableImages.length <= 1) return;

    const startAutoSlide = () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = setInterval(() => {
        setCurrentImageIndex((prev) =>
          prev < availableImages.length - 1 ? prev + 1 : 0,
        );
      }, 3000); // Smooth 3-second intervals
    };

    const stopAutoSlide = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    startAutoSlide();
    return () => stopAutoSlide();
  }, [availableImages.length]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return (
    <Card padding>
      <Grid columns={["fill"]} rows={["auto", "2fr", "auto"]} spacing="tight">
        <View>
          {/* Larger Auto-Sliding Image */}
          {availableImages.length > 0 && (
            <View>
              <Image
                source={currentImage?.url || ""}
                fit="cover"
                aspectRatio={1.5}
              />
            </View>
          )}
        </View>
        <BlockStack spacing="tight">
          <TextBlock size="small" emphasis="bold">
            {product.title}
          </TextBlock>
          <TextBlock size="medium" emphasis="bold">
            {product.price}
          </TextBlock>

          {/* Variant Information - Compact */}
          {product.variants && product.variants.length > 0 && (
            <TextBlock size="small" appearance="subdued">
              {product.variants.length} variant
              {product.variants.length > 1 ? "s" : ""} available
            </TextBlock>
          )}

          <TextBlock size="small" appearance="success">
            ✓ In Stock
          </TextBlock>
        </BlockStack>
        <Button
          kind="primary"
          onPress={async () => {
            try {
              await onShopNow(product.id, position, product.url);
            } catch (error) {
              logger.error(
                {
                  error: error instanceof Error ? error.message : String(error),
                },
                "Failed to track recommendation click",
              );
            }
          }}
        >
          Shop Now
        </Button>
      </Grid>
    </Card>
  );
}
