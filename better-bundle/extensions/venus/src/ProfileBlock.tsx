import {
  Grid,
  reactExtension,
  TextBlock,
  Button,
  Image,
  View,
  Style,
  SkeletonText,
  SkeletonImage,
  Card,
  BlockStack,
  useAuthenticatedAccountCustomer,
  useNavigation,
} from "@shopify/ui-extensions-react/customer-account";
import { useState, useEffect } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
} from "./api/recommendations";
import { analyticsApi, type ViewedProduct } from "./api/analytics";

export default reactExtension("customer-account.profile.block.render", () => (
  <ProfileBlock />
));

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

function ProfileBlock() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { navigate } = useNavigation();
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(
    () =>
      `venus_profile_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
  );

  const trackRecommendationClick = async (
    productId: string,
    position: number,
    productUrl: string,
  ) => {
    try {
      await analyticsApi.trackInteraction({
        session_id: sessionId,
        product_id: productId,
        interaction_type: "click",
        position,
        extension_type: "venus",
        context: "profile",
        metadata: { source: "view_product_button" },
      });

      // Add attribution parameters to track recommendation source
      // Create a deterministic short reference using a simple hash
      const shortRef = sessionId
        .split("")
        .reduce((hash, char) => {
          return ((hash << 5) - hash + char.charCodeAt(0)) & 0xffffffff;
        }, 0)
        .toString(36)
        .substring(0, 6);

      const attributionParams = new URLSearchParams({
        ref: shortRef,
        src: productId,
        pos: position.toString(),
      });

      // Navigate to product page with attribution
      const productUrlWithAttribution = `${productUrl}?${attributionParams.toString()}`;
      navigate(productUrlWithAttribution);

      console.log(
        "View product tracked and navigating to:",
        productUrlWithAttribution,
      );
    } catch (error) {
      console.error("Failed to track click:", error);
    }
  };

  // Create recommendation session and fetch recommendations
  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await recommendationApi.getRecommendations({
          context: "profile",
          limit: 4,
          user_id: customerId,
        });

        if (response.success && response.recommendations) {
          // Transform API response to component format
          const transformedProducts: Product[] = response.recommendations.map(
            (rec: ProductRecommendation) => ({
              id: rec.id,
              title: rec.title,
              handle: rec.handle,
              price: `${rec.price.currency_code} ${rec.price.amount}`,
              image: rec.image?.url,
              inStock: rec.available ?? true,
              url: rec.url,
            }),
          );

          setProducts(transformedProducts);

          // Create recommendation session with viewed products in single call
          const viewedProducts: ViewedProduct[] = transformedProducts.map(
            (product, index) => ({
              product_id: product.id,
              position: index + 1,
            }),
          );

          await analyticsApi.createSession({
            extension_type: "venus",
            context: "profile",
            user_id: customerId,
            session_id: sessionId,
            viewed_products: viewedProducts,
            metadata: { source: "profile_page" },
          });
        } else {
          throw new Error("Failed to fetch recommendations");
        }
      } catch (err) {
        console.error("Error fetching recommendations:", err);
        setError("Failed to load recommendations");
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [customerId]);

  // Loading skeleton component
  const SkeletonCard = () => (
    <Card padding>
      <Grid
        columns={["fill"]}
        rows={Style.default(["auto", "1fr", "auto"])
          .when({ viewportInlineSize: { min: "extraSmall" } }, [
            "auto",
            "1.5fr",
            "auto",
          ])
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
            "3fr",
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
            <SkeletonImage aspectRatio={1.2} />
          </View>

          {/* Mobile: Compact aspect ratio */}
          <View
            display={Style.default("none")
              .when({ viewportInlineSize: { min: "extraSmall" } }, "auto")
              .when({ viewportInlineSize: { min: "small" } }, "none")}
          >
            <SkeletonImage aspectRatio={1.1} />
          </View>

          {/* Tablet: Slightly wider */}
          <View
            display={Style.default("none")
              .when({ viewportInlineSize: { min: "small" } }, "auto")
              .when({ viewportInlineSize: { min: "medium" } }, "none")}
          >
            <SkeletonImage aspectRatio={1.0} />
          </View>

          {/* Desktop: Moderate aspect ratio */}
          <View
            display={Style.default("none").when(
              { viewportInlineSize: { min: "medium" } },
              "auto",
            )}
          >
            <SkeletonImage aspectRatio={0.9} />
          </View>
        </View>
        <BlockStack spacing="tight">
          <SkeletonText size="medium" />
          <SkeletonText size="large" />
          <SkeletonText size="small" />
        </BlockStack>
        <Grid columns={["fill", "fill"]} spacing="tight">
          <View padding="none" border="base" cornerRadius="base">
            <SkeletonText size="small" />
          </View>
          <View padding="none" border="base" cornerRadius="base">
            <SkeletonText size="small" />
          </View>
        </Grid>
      </Grid>
    </Card>
  );

  if (loading) {
    return (
      <BlockStack spacing="base">
        <BlockStack spacing="tight">
          <SkeletonText size="large" />
          <SkeletonText size="medium" />
        </BlockStack>
        <Grid
          columns={Style.default(["fill"])
            .when({ viewportInlineSize: { min: "extraSmall" } }, ["fill"])
            .when({ viewportInlineSize: { min: "small" } }, ["fill", "fill"])
            .when({ viewportInlineSize: { min: "medium" } }, [
              "fill",
              "fill",
              "fill",
            ])
            .when({ viewportInlineSize: { min: "large" } }, [
              "fill",
              "fill",
              "fill",
              "fill",
            ])}
          spacing="base"
        >
          {Array.from({ length: 3 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </Grid>
      </BlockStack>
    );
  }

  // Don't render anything if there's an error or no products
  if (error || products.length === 0) {
    return null;
  }

  return (
    <BlockStack spacing="base">
      <BlockStack spacing="tight">
        <TextBlock size="large" emphasis="bold">
          Recommended for You
        </TextBlock>
        <TextBlock appearance="subdued">Curated just for you</TextBlock>
      </BlockStack>
      <Grid
        columns={Style.default(["fill"])
          .when({ viewportInlineSize: { min: "extraSmall" } }, ["fill"])
          .when({ viewportInlineSize: { min: "small" } }, ["fill", "fill"])
          .when({ viewportInlineSize: { min: "medium" } }, [
            "fill",
            "fill",
            "fill",
          ])
          .when({ viewportInlineSize: { min: "large" } }, [
            "fill",
            "fill",
            "fill",
            "fill",
          ])}
        spacing="base"
      >
        {products.map((product, index) => (
          <Card key={product.id} padding>
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
                onPress={() =>
                  trackRecommendationClick(product.id, index + 1, product.url)
                }
              >
                Shop Now
              </Button>
            </Grid>
          </Card>
        ))}
      </Grid>
    </BlockStack>
  );
}
