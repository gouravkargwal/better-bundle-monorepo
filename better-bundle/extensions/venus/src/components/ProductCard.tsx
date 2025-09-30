import {
  Grid,
  TextBlock,
  Button,
  Image,
  View,
  Style,
  Card,
  BlockStack,
} from "@shopify/ui-extensions-react/customer-account";

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
  return (
    <Card padding>
      <Grid
        columns={["fill"]}
        rows={Style.default(["auto", "2fr", "1fr"]) // extraSmall: smaller image and content
          .when({ viewportInlineSize: { min: "small" } }, [
            "auto",
            "2fr",
            "1fr",
          ])
          .when({ viewportInlineSize: { min: "medium" } }, [
            "auto",
            "2.5fr",
            "1fr",
          ])
          .when({ viewportInlineSize: { min: "large" } }, [
            "auto",
            "2fr",
            "1fr",
          ])}
        spacing="base"
      >
        <View>
          {/* Ultra Mobile: Very compact */}
          <View
            display={Style.default("auto").when(
              { viewportInlineSize: { min: "extraSmall" } },
              "none",
            )}
          >
            <Image source={product.image} fit="cover" aspectRatio={2} />
          </View>

          {/* Mobile: Compact aspect ratio */}
          <View
            display={Style.default("none")
              .when({ viewportInlineSize: { min: "extraSmall" } }, "auto")
              .when({ viewportInlineSize: { min: "small" } }, "none")}
          >
            <Image source={product.image} fit="cover" aspectRatio={2} />
          </View>

          {/* Tablet: Slightly wider */}
          <View
            display={Style.default("none")
              .when({ viewportInlineSize: { min: "small" } }, "auto")
              .when({ viewportInlineSize: { min: "medium" } }, "none")}
          >
            <Image source={product.image} fit="cover" aspectRatio={1.1} />
          </View>

          {/* Desktop: Moderate aspect ratio */}
          <View
            display={Style.default("none").when(
              { viewportInlineSize: { min: "medium" } },
              "auto",
            )}
          >
            <Image source={product.image} fit="cover" aspectRatio={1.2} />
          </View>
        </View>
        <BlockStack spacing="tight">
          <TextBlock size="medium" emphasis="bold">
            {product.title}
          </TextBlock>
          <TextBlock size="large" emphasis="bold">
            {product.price}
          </TextBlock>
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
              console.error("Failed to handle shop now:", error);
            }
          }}
        >
          Shop Now
        </Button>
      </Grid>
    </Card>
  );
}
