import { render } from "preact";
import { useMemo } from "preact/hooks";
import { useRecommendations } from "./hooks/useRecommendations.js";
import { recordOfferOutcome } from "./api/analytics.js";
import { logger } from "./utils/logger.js";

/**
 * Thank You page recommendations.
 *
 * Target: `purchase.thank-you.block.render`.
 *
 * The widest-reach post-purchase surface available. The checkout block is
 * Shopify Plus only and the post-purchase interstitial renders only when the
 * card was vaulted; this block works on every plan for every order.
 *
 * The order is complete here, so the extension has read access only — no cart
 * writes, no order edits. That shapes the whole component:
 *
 *   - The offer is a link to the product's own page, not an add button. There
 *     is also no programmatic navigation in this sandbox, so the link must be
 *     declarative: `s-link` with an href, not a click handler that navigates.
 *   - Attribution is therefore click-through only. The click is reported
 *     against its impression and the backend credits it if that product turns
 *     up in a paid order inside the window. That path over-credits by nature,
 *     which is what the held-out control group corrects for.
 *
 * Every component and attribute here is either already proven in Checkout.jsx
 * or taken from the Polaris web components reference for this API version.
 */

export default async () => {
  render(<ThankYouRecommendations />, document.body);
};

function ThankYouRecommendations() {
  const { lines, cost, buyerIdentity, storage } = shopify;
  const shopDomain = shopify.shop.myshopifyDomain;
  const customerId = buyerIdentity?.customer?.value?.id || null;

  // What was just bought. `lines` stays readable on this target and is the
  // query key the edge lookup needs.
  const purchasedProductIds = useMemo(() => {
    return (
      lines.value
        ?.map((line) => {
          const productId = line.merchandise?.product?.id;
          if (!productId) return null;
          // Lines carry GIDs; the backend keys on the numeric id.
          return productId.startsWith("gid://shopify/Product/")
            ? productId.split("/").pop()
            : productId;
        })
        .filter(Boolean) || []
    );
  }, [lines.value]);

  // Drives the price ceiling. The order is paid, so a larger add-on is a more
  // reasonable ask here than it would be mid-checkout.
  const orderValue = Number(cost?.totalAmount?.value?.amount || 0);

  const { loading, products, error } = useRecommendations({
    context: "thank_you_page",
    limit: 3,
    customerId,
    shopDomain,
    storage,
    cartItems: purchasedProductIds,
    cartValue: orderValue,
    checkoutStep: "thank_you",
  });

  // Render nothing rather than an empty frame. Someone who has just paid
  // should not be shown a broken widget, and nor should the merchant.
  if (loading || error || !products?.length) {
    if (error) {
      logger.error({ error }, "Mercury ThankYou: recommendations failed");
    }
    return null;
  }

  // Fired as the link is followed. Not awaited — navigation happens either way,
  // and the request carries keepalive so it survives the page leaving.
  const reportClick = (product) => {
    if (!product.impression_id) return;
    recordOfferOutcome(product.impression_id, "clicked").catch((err) =>
      logger.error({ err }, "Mercury ThankYou: click report failed"),
    );
  };

  return (
    <s-section heading="You might also like">
      <s-stack direction="block" gap="base">
        {products.map((product) => (
          <s-box
            key={product.id}
            padding="base"
            border="base"
            borderWidth="base"
            borderRadius="base"
          >
            <s-stack direction="inline" gap="base" alignItems="center">
              {product.image?.url && (
                <s-image
                  src={product.image.url}
                  alt={product.image.alt_text || product.title}
                  aspectRatio="1/1"
                  inlineSize="fill"
                  objectFit="cover"
                  borderRadius="base"
                  loading="lazy"
                />
              )}

              <s-stack direction="block" gap="small-500">
                <s-text>{product.title}</s-text>
                <s-text type="strong">{product.price}</s-text>
              </s-stack>

              {/* Declarative navigation: there is no window.open in this
                  sandbox, and target="_blank" keeps the order confirmation
                  open behind the product page. */}
              <s-link
                href={product.url}
                target="_blank"
                accessibilityLabel={`View ${product.title}`}
                onClick={() => reportClick(product)}
              >
                View
              </s-link>
            </s-stack>
          </s-box>
        ))}
      </s-stack>
    </s-section>
  );
}
