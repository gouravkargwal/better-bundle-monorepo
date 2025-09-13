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
  Link,
} from "@shopify/ui-extensions-react/customer-account";
import { useState, useEffect } from "react";
import {
  recommendationApi,
  type ProductRecommendation,
} from "./api/recommendations";

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
}

function ProfileBlock() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { navigate } = useNavigation();
  // Fetch real product recommendations
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
            }),
          );

          setProducts(transformedProducts);
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
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </Grid>
      </BlockStack>
    );
  }

  // Don't render anything if there's an error
  if (error) {
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
        {products.map((product) => (
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
              <Grid columns={["fill", "fill"]} spacing="tight">
                <Link to={`/products/${product.handle}`}>View Product</Link>
                <Button
                  kind="secondary"
                  onPress={() => {
                    // Add to cart functionality
                    console.log(
                      "Add to cart:",
                      product.id,
                      "handle:",
                      product.handle,
                    );
                  }}
                >
                  Add to Cart
                </Button>
              </Grid>
            </Grid>
          </Card>
        ))}
      </Grid>
    </BlockStack>
  );
}
