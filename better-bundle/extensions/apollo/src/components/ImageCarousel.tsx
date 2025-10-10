import { useState, useCallback } from "react";
import {
  View,
  Image,
  InlineStack,
  Button,
  Text,
} from "@shopify/post-purchase-ui-extensions-react";

interface ImageCarouselProps {
  images: {
    url: string;
    alt_text?: string;
  }[];
  productTitle: string;
}

export function ImageCarousel({ images, productTitle }: ImageCarouselProps) {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [showAllThumbnails, setShowAllThumbnails] = useState(false);

  const handleThumbnailClick = useCallback((index: number) => {
    setCurrentImageIndex(index);
  }, []);

  const toggleShowAll = useCallback(() => {
    setShowAllThumbnails((prev) => !prev);
  }, []);

  // Don't render carousel if there's only one image or no images
  if (!images || images.length <= 1) {
    return (
      // @ts-ignore
      <View>
        {/* @ts-ignore */}
        <Image source={images?.[0]?.url || ""} description={productTitle} />
      </View>
    );
  }

  return (
    // @ts-ignore
    <View>
      {/* Main Image Container - Large and Prominent */}
      {/* @ts-ignore */}
      <View blockPadding="base">
        {/* @ts-ignore */}
        <Image
          source={images[currentImageIndex]?.url || ""}
          description={productTitle}
        />
      </View>

      {/* Thumbnail Gallery */}
      {/* @ts-ignore */}
      <View blockPadding="base" alignment="center">
        {/* First row - Always show first 4 images */}
        {/* @ts-ignore */}
        <InlineStack spacing="tight" alignment="center">
          {images.slice(0, 4).map((image, index) => (
            // @ts-ignore
            <Button
              key={index}
              plain
              onPress={() => handleThumbnailClick(index)}
            >
              {/* @ts-ignore */}
              <View
                blockPadding="tight"
                inlinePadding="tight"
                border={index === currentImageIndex ? "base" : "none"}
                cornerRadius="small"
                alignment="center"
              >
                {/* @ts-ignore */}
                <Image
                  source={image.url}
                  description={`${productTitle} - Image ${index + 1}`}
                />
              </View>
            </Button>
          ))}
        </InlineStack>

        {/* Second row - Show additional images if expanded */}
        {showAllThumbnails && images.length > 4 && (
          // @ts-ignore
          <InlineStack spacing="tight" alignment="center" blockPadding="tight">
            {images.slice(4).map((image, index) => (
              // @ts-ignore
              <Button
                key={index + 4}
                plain
                onPress={() => handleThumbnailClick(index + 4)}
              >
                {/* @ts-ignore */}
                <View
                  blockPadding="tight"
                  inlinePadding="tight"
                  border={index + 4 === currentImageIndex ? "base" : "none"}
                  cornerRadius="small"
                  alignment="center"
                >
                  {/* @ts-ignore */}
                  <Image
                    source={image.url}
                    description={`${productTitle} - Image ${index + 5}`}
                  />
                </View>
              </Button>
            ))}
          </InlineStack>
        )}

        {/* Toggle button for more images */}
        {images.length > 4 && (
          // @ts-ignore
          <View blockPadding="tight" alignment="center">
            {/* @ts-ignore */}
            <Button plain onPress={toggleShowAll}>
              {/* @ts-ignore */}
              <Text size="small" alignment="center">
                {showAllThumbnails
                  ? "Show less"
                  : `+${images.length - 4} more images`}
              </Text>
            </Button>
          </View>
        )}
      </View>
    </View>
  );
}
