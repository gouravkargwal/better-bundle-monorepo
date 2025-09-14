import {
  Grid,
  View,
  Style,
  SkeletonText,
  SkeletonImage,
  Card,
  BlockStack,
} from "@shopify/ui-extensions-react/customer-account";

interface SkeletonGridProps {
  columns?: {
    extraSmall?: number;
    small?: number;
    medium?: number;
    large?: number;
  };
  count?: number;
}

export function SkeletonGrid({
  columns = {
    extraSmall: 1,
    small: 2,
    medium: 3,
    large: 4,
  },
  count = 3,
}: SkeletonGridProps) {
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
        <View padding="none" border="base" cornerRadius="base">
          <SkeletonText size="small" />
        </View>
      </Grid>
    </Card>
  );

  return (
    <Grid columns={columnsConfig} spacing="base">
      {Array.from({ length: count }).map((_, index) => (
        <SkeletonCard key={index} />
      ))}
    </Grid>
  );
}
