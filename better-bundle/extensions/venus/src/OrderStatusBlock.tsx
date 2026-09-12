import { useMemo } from "react";
import {
  BlockStack,
  reactExtension,
  Divider,
  useAuthenticatedAccountCustomer,
  useShop,
  useNavigation,
  useExtensionEditor,
  useCartLines,
  TextBlock,
  SkeletonText,
} from "@shopify/ui-extensions-react/customer-account";
import { ProductGrid } from "./components/ProductGrid";
import { SkeletonGrid } from "./components/SkeletonGrid";
import { useSettledSkeleton } from "./hooks/useSettledSkeleton";
import { useRecommendations } from "./hooks/useRecommendations";

export default reactExtension(
  "customer-account.order-status.block.render",
  () => <OrderStatusWithRecommendations />,
);

// Placeholder thumbnail as an inline SVG data URI rather than a remote asset:
// no network request, nothing to 404, and no CDN host to allowlist. ProductCard
// renders no image area at all when `image` is null, which would show the
// merchant a layout narrower than the real one.
const SAMPLE_IMAGE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
       <rect width="120" height="120" fill="#f1f2f4"/>
       <path d="M30 78l18-22 14 17 10-12 18 17H30z" fill="#c9cccf"/>
       <circle cx="45" cy="42" r="8" fill="#c9cccf"/>
     </svg>`,
  );

// Sample content for the editor preview only. Never fetched, never billed.
const EDITOR_SAMPLE_PRODUCTS = [
  {
    id: "sample-1",
    title: "Example product",
    handle: "example-product",
    price: "$24.99",
    image: { url: SAMPLE_IMAGE, alt_text: "Example product" },
    inStock: true,
    url: "#",
  },
  {
    id: "sample-2",
    title: "Another example",
    handle: "another-example",
    price: "$39.00",
    image: { url: SAMPLE_IMAGE, alt_text: "Another example" },
    inStock: true,
    url: "#",
  },
];

function OrderStatusWithRecommendations() {
  const { id: customerId } = useAuthenticatedAccountCustomer();
  const { myshopifyDomain } = useShop();
  const { navigate } = useNavigation();
  const lines = useCartLines();

  const purchasedProductIds = useMemo(() => {
    return (
      lines
        ?.map((line) => {
          const productId = line.merchandise?.product?.id;
          if (!productId) return null;
          return productId.startsWith("gid://shopify/Product/")
            ? productId.split("/").pop()
            : productId;
        })
        .filter(Boolean) as string[]
    ) || [];
  }, [lines]);

  // Are we rendering in the Checkout & Accounts editor rather than a real
  // order status page?
  //
  // Undefined on a live page, an Editor object in the editor. Without this,
  // every merchant who opens the customiser to position this block fires a
  // real recommendation request and writes real `offer_impressions` rows — so
  // their own configuring appears in their impact dashboard as offers shown to
  // shoppers who never existed, dragging the conversion rate down.
  //
  // Phoenix gets this from Liquid's `request.design_mode` and mercury from
  // `shopify.extension.editor`; this is the customer-account equivalent.
  const editor = useExtensionEditor();
  const inEditor = Boolean(editor);

  const {
    loading,
    products,
    error,
    trackRecommendationClick,
    columnConfig,
  } = useRecommendations({
    // Nothing is fetched in the editor: no request, no impression row.
    // Also skip while cart lines are loading (lines is undefined or empty) to prevent
    // an initial empty request that falls back to baseline and double-logs impressions.
    skip: inEditor || !lines || lines.length === 0,
    context: "order_status",
    limit: 2,
    customerId,
    shopDomain: myshopifyDomain,
    productIds: purchasedProductIds,
    columnConfig: {
      extraSmall: 1, // 1 column on very small screens
      small: 2, // 2 columns on small screens
      medium: 2, // 2 columns on medium screens
      large: 2, // 2 columns on large screens
    },
  });

  const showSkeleton = useSettledSkeleton(loading);

  // No view reporting: the impression row is written server-side the moment
  // recommendations are served, so the client has nothing to add.

  // Override trackRecommendationClick to include navigation
  const handleShopNow = async (
    productId: string,
    position: number,
    productUrl: string,
    impressionId?: string,
  ) => {
    const url = await trackRecommendationClick(
      productId,
      position,
      productUrl,
      impressionId,
    );
    navigate(url);
  };

  // The editor must always render something, or the merchant cannot see the
  // block to position it — Shopify's guidance is to guarantee a preview even
  // when the live conditions are not met. Sample content through the real grid,
  // so what the merchant approves is the anatomy a shopper will get. Costs no
  // request and writes no impression.
  if (inEditor) {
    return (
      <BlockStack spacing="base">
        <Divider />
        <BlockStack spacing="tight">
          <TextBlock size="large" emphasis="bold">
            You Might Also Like
          </TextBlock>
          <TextBlock appearance="subdued">
            Discover more products based on your order
          </TextBlock>
        </BlockStack>
        <ProductGrid
          products={EDITOR_SAMPLE_PRODUCTS}
          onShopNow={async () => {}}
          columns={columnConfig}
        />
        <TextBlock appearance="subdued" size="small">
          Example only — shoppers see real recommendations here.
        </TextBlock>
      </BlockStack>
    );
  }

  // Two states while the request is out, not one. Until the delay elapses we
  // render nothing at all, because we do not yet know whether anything is
  // coming — the shopper could be in the holdout, or this order may have no
  // recommendations. Painting a skeleton and then removing it reads as a
  // crashed widget. See useSettledSkeleton.
  if (loading) {
    if (!showSkeleton) {
      return null;
    }
    return (
      <BlockStack spacing="base">
        <Divider />
        <BlockStack spacing="tight">
          <SkeletonText size="large" />
          <SkeletonText size="medium" />
        </BlockStack>
        <SkeletonGrid columns={columnConfig} count={3} />
      </BlockStack>
    );
  }

  // Don't render recommendations if there's an error or no products
  if (error || products.length === 0) {
    return (
      <BlockStack spacing="base">
        <Divider />
      </BlockStack>
    );
  }

  return (
    <BlockStack spacing="base">
      <Divider />
      <BlockStack spacing="tight">
        <TextBlock size="large" emphasis="bold">
          You Might Also Like
        </TextBlock>
        <TextBlock appearance="subdued">
          Discover more products based on your order
        </TextBlock>
      </BlockStack>
      <ProductGrid
        products={products}
        onShopNow={handleShopNow}
        columns={columnConfig}
      />
    </BlockStack>
  );
}
