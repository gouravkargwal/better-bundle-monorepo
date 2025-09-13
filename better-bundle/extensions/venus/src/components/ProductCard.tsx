import {
  Card,
  TextBlock,
  Image,
  InlineStack,
  BlockStack,
  Button,
  useApi,
  Link,
} from "@shopify/ui-extensions-react/customer-account";
import type { ProductRecommendation } from "../api/recommendations";

interface ProductCardProps {
  product: ProductRecommendation;
  onAddToCart?: (productId: string) => void;
}

export function ProductCard({ product, onAddToCart }: ProductCardProps) {
  const { i18n } = useApi();

  const formatPrice = (price: { amount: string; currency_code: string }) => {
    return new Intl.NumberFormat(i18n.locale, {
      style: "currency",
      currency: price.currency_code,
    }).format(parseFloat(price.amount));
  };

  const hasDiscount =
    product.compare_at_price &&
    parseFloat(product.compare_at_price.amount) >
      parseFloat(product.price.amount);

  return (
    <Card>
      <BlockStack spacing="tight">
        {/* Product Image */}
        {product.image && (
          <Image
            source={product.image.url}
            alt={product.image.alt_text || product.title}
            aspectRatio={1}
            fit="cover"
          />
        )}

        {/* Product Info */}
        <BlockStack spacing="extraTight">
          <TextBlock size="small" emphasis="strong">
            {product.title}
          </TextBlock>

          {product.vendor && (
            <TextBlock size="small" appearance="subdued">
              {product.vendor}
            </TextBlock>
          )}

          {/* Price */}
          <InlineStack spacing="tight" blockAlignment="center">
            <TextBlock size="small" emphasis="strong">
              {formatPrice(product.price)}
            </TextBlock>
            {hasDiscount && (
              <TextBlock size="small" appearance="subdued">
                <s>{formatPrice(product.compare_at_price!)}</s>
              </TextBlock>
            )}
          </InlineStack>

          {/* Availability */}
          {product.available === false && (
            <TextBlock size="small" appearance="critical">
              {i18n.translate("outOfStock")}
            </TextBlock>
          )}
        </BlockStack>

        {/* Action Button */}
        <Button
          kind="secondary"
          size="small"
          onPress={() => onAddToCart?.(product.id)}
          disabled={product.available === false}
        >
          {i18n.translate("viewProduct")}
        </Button>
      </BlockStack>
    </Card>
  );
}
