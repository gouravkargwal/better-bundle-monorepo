import {
  reactExtension,
  Banner,
  BlockStack,
  Button,
  Heading,
  Image,
  InlineLayout,
  Text,
  useApi,
  useApplyAttributeChange,
  useApplyCartLinesChange,
  useCartLines,
  useInstructions,
  useSettings,
  useTranslate,
  useShop,
} from "@shopify/ui-extensions-react/checkout";
import { useState, useEffect } from "react";

// 1. Choose an extension target
export default reactExtension("purchase.checkout.block.render", () => (
  <Extension />
));

// Product recommendation interface
interface Product {
  id: string;
  title: string;
  handle: string;
  image: string;
  price: string;
  currency: string;
  variantId: string;
  reason?: string;
}

// Recommendation card component
function RecommendationCard({
  product,
  onAddToCart,
  loading,
  translate,
}: {
  product: Product;
  onAddToCart: (product: Product) => void;
  loading: boolean;
  translate: any;
}) {
  return (
    <BlockStack
      spacing="tight"
      border="base"
      padding="base"
      cornerRadius="base"
    >
      <InlineLayout
        columns={["auto", "fill"]}
        spacing="base"
        blockAlignment="start"
      >
        <Image
          source={product.image}
          aspectRatio={1}
          fit="cover"
          cornerRadius="small"
        />
        <BlockStack spacing="tight">
          <Text size="medium" emphasis="bold">
            {product.title}
          </Text>
          <Text size="large" emphasis="bold" appearance="accent">
            {product.currency} {product.price}
          </Text>
          {product.reason && (
            <Text size="small" appearance="subdued">
              {product.reason}
            </Text>
          )}
          <Button
            onPress={() => onAddToCart(product)}
            loading={loading}
            kind="primary"
          >
            {translate("addToCart")}
          </Button>
        </BlockStack>
      </InlineLayout>
    </BlockStack>
  );
}

// Loading spinner component
function LoadingSpinner({ translate }: { translate: any }) {
  return (
    <BlockStack
      spacing="tight"
      padding="base"
      border="base"
      cornerRadius="base"
    >
      <Text appearance="subdued" emphasis="bold">
        {translate("loadingRecommendations")}
      </Text>
    </BlockStack>
  );
}

// Main extension component
function Extension() {
  const translate = useTranslate();
  const { extension } = useApi();
  const instructions = useInstructions();
  const applyAttributeChange = useApplyAttributeChange();
  const applyCartLinesChange = useApplyCartLinesChange();
  const cartLines = useCartLines();
  const settings = useSettings();
  const shop = useShop();

  const [recommendations, setRecommendations] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [addingToCart, setAddingToCart] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Note: We'll handle cart update errors gracefully in the addToCartWithAttribution function

  // Load recommendations on component mount
  useEffect(() => {
    loadRecommendations();
  }, []);

  const loadRecommendations = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get cart product IDs for context
      const cartProductIds = cartLines.map((line) =>
        line.merchandise.product.id.replace("gid://shopify/Product/", ""),
      );

      // Build API request
      const backendUrl =
        settings.backend_url || "https://your-python-worker.com";
      const apiUrl = `${backendUrl}/api/v1/recommendations/`;

      const requestBody = {
        shop_domain: shop.myshopifyDomain,
        context: "checkout",
        product_id: cartProductIds[0] || null, // Use first cart item as context
        user_id: null, // Will be null for guest checkout
        session_id: null, // Will be null for guest checkout
        limit: settings.recommendation_limit || 3,
      };

      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const data = await response.json();

      // Mock data for testing when backend is not available
      if (!data.success || !data.recommendations) {
        console.log("Backend unavailable, using mock data for testing");
        const mockRecommendations = [
          {
            id: "gid://shopify/Product/1234567890",
            title: "Test Product 1",
            handle: "test-product-1",
            image: getDefaultImage(),
            price: "19.99",
            currency: "USD",
            variantId: "gid://shopify/ProductVariant/1234567890",
            reason: "Frequently bought together",
          },
          {
            id: "gid://shopify/Product/1234567891",
            title: "Test Product 2",
            handle: "test-product-2",
            image: getDefaultImage(),
            price: "29.99",
            currency: "USD",
            variantId: "gid://shopify/ProductVariant/1234567891",
            reason: "Customers also bought",
          },
        ];

        const transformedRecommendations = mockRecommendations.map(
          (rec: any) => ({
            id: rec.id,
            title: rec.title,
            handle: rec.handle,
            image: rec.image,
            price: rec.price,
            currency: rec.currency,
            variantId: rec.variantId,
            reason: rec.reason,
          }),
        );

        setRecommendations(transformedRecommendations);
        return;
      }

      if (data.success && data.recommendations) {
        // Transform API response to our Product interface
        const transformedRecommendations = data.recommendations.map(
          (rec: any) => ({
            id: rec.id,
            title: rec.title,
            handle: rec.handle,
            image: rec.image || getDefaultImage(),
            price: rec.price,
            currency: rec.currency || "USD",
            variantId: rec.variantId || rec.id, // Fallback to product ID if no variant
            reason: rec.reason,
          }),
        );

        setRecommendations(transformedRecommendations);
      } else {
        setRecommendations([]);
      }
    } catch (err) {
      console.error("Failed to load recommendations:", err);

      // If it's a network error, use mock data instead of showing error
      if (err instanceof TypeError && err.message.includes("Failed to fetch")) {
        console.log("Network error, using mock data for testing");
        const mockRecommendations = [
          {
            id: "gid://shopify/Product/1234567890",
            title: "Test Product 1",
            handle: "test-product-1",
            image: getDefaultImage(),
            price: "19.99",
            currency: "INR",
            variantId: "gid://shopify/ProductVariant/1234567890",
            reason: "Frequently bought together",
          },
          {
            id: "gid://shopify/Product/1234567891",
            title: "Test Product 2",
            handle: "test-product-2",
            image: getDefaultImage(),
            price: "29.99",
            currency: "INR",
            variantId: "gid://shopify/ProductVariant/1234567891",
            reason: "Customers also bought",
          },
        ];

        const transformedRecommendations = mockRecommendations.map(
          (rec: any) => ({
            id: rec.id,
            title: rec.title,
            handle: rec.handle,
            image: rec.image,
            price: rec.price,
            currency: rec.currency,
            variantId: rec.variantId,
            reason: rec.reason,
          }),
        );

        setRecommendations(transformedRecommendations);
        return;
      }

      setError("Failed to load recommendations");
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  };

  const addToCartWithAttribution = async (product: Product) => {
    try {
      setAddingToCart(product.id);

      // Generate unique attribution ID
      const attributionId = `ui_attr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // Add product to cart
      const result = await applyCartLinesChange({
        type: "addCartLine",
        merchandiseId: product.variantId,
        quantity: 1,
      });

      // Store attribution in cart attributes
      await applyAttributeChange({
        key: "betterbundle_ui_attributions",
        type: "updateAttribute",
        value: JSON.stringify({
          id: attributionId,
          extension_type: "checkout",
          product_id: product.id,
          timestamp: Date.now(),
          source: "mercury_extension",
        }),
      });

      // Track the interaction
      trackRecommendationInteraction(product, "add_to_cart");

      console.log("Product added to cart with attribution:", result);
    } catch (err) {
      console.error("Failed to add product to cart:", err);
    } finally {
      setAddingToCart(null);
    }
  };

  const trackRecommendationInteraction = (product: Product, action: string) => {
    // Send interaction to backend for analytics
    const backendUrl = settings.backend_url || "https://your-python-worker.com";
    const analyticsUrl = `${backendUrl}/api/analytics/track`;

    fetch(analyticsUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: `recommendation_${action}`,
        product_id: product.id,
        shop_domain: shop.myshopifyDomain,
        extension_type: "checkout",
        timestamp: Date.now(),
      }),
    }).catch((err) => {
      console.error("Failed to track interaction:", err);
    });
  };

  const getDefaultImage = () => {
    return "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==";
  };

  // Don't show if no recommendations and not loading
  if (!loading && recommendations.length === 0) {
    return null;
  }

  return (
    <BlockStack spacing="base" border="base" padding="base" cornerRadius="base">
      <Heading level={2}>
        {settings.recommendation_title || translate("lastChanceToAdd")}
      </Heading>

      {loading && <LoadingSpinner translate={translate} />}

      {error && (
        <Banner status="critical">
          {translate("failedToLoadRecommendations")}
        </Banner>
      )}

      {!loading && recommendations.length > 0 && (
        <BlockStack spacing="base">
          {recommendations.map((product) => (
            <RecommendationCard
              key={product.id}
              product={product}
              onAddToCart={addToCartWithAttribution}
              loading={addingToCart === product.id}
              translate={translate}
            />
          ))}
        </BlockStack>
      )}
    </BlockStack>
  );
}
