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

  // Rendering in the checkout editor, not on a real thank-you page.
  // `shopify.extension.editor` is undefined on a live page. Without this a
  // merchant configuring the block generates real recommendation requests and
  // real `offer_impressions` rows, so their own setup work lands in their
  // impact dashboard as offers shown to shoppers who never existed.
  const inEditor = Boolean(shopify.extension?.editor);

  const { loading, products, error } = useRecommendations({
    // No request and no impression while the merchant is configuring.
    skip: inEditor,
    context: "thank_you_page",
    limit: 3,
    customerId,
    shopDomain,
    storage,
    cartItems: purchasedProductIds,
    cartValue: orderValue,
    checkoutStep: "thank_you",
  });

  // Dummy content in the editor, so the merchant can see how the block looks
  // and where it sits. This matters more here than in checkout: the live
  // branch below returns null when there is nothing to show, so without this
  // the editor would render an empty frame and the merchant would have no
  // block to position at all.
  //
  // Deliberately the same markup as the real cards, so what they are
  // positioning is what shoppers will see.
  if (inEditor) {
    // Dummy content so the merchant can see how the block looks and where it
    // sits. It matters more here than in checkout: the live branch below
    // returns null when there is nothing to show, so without this the editor
    // would render an empty frame and there would be no block to position.
    const samples = [
      { title: "Example product", variant: "Small / Black", price: "$24.99" },
      { title: "Another product", variant: "One size", price: "$34.99" },
    ];
    return (
      <s-section heading="You might also like">
        <s-stack direction="block" gap="base">
          {samples.map((sample) => (
            <s-stack
                key={sample.title}
                direction="inline"
                gap="base"
                alignItems="center"
                justifyContent="space-between"
              >
                <s-stack direction="inline" gap="base" alignItems="center">
                  <s-product-thumbnail alt={sample.title} size="base" />
                  <s-stack direction="block" gap="small-500">
                    <s-text>{sample.title}</s-text>
                    <s-text color="subdued" type="small">
                      {sample.variant}
                    </s-text>
                  </s-stack>
                </s-stack>
                <s-stack direction="block" gap="small-500" alignItems="end">
                  <s-text type="strong">{sample.price}</s-text>
                  <s-text color="subdued">View</s-text>
                </s-stack>
              </s-stack>
          ))}
          <s-text color="subdued" type="small">
            Example only — shoppers see real recommendations here.
          </s-text>
        </s-stack>
      </s-section>
    );
  }

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
          <s-stack
              key={product.id}
              direction="inline"
              gap="base"
              alignItems="center"
              justifyContent="space-between"
            >
              <s-stack direction="inline" gap="base" alignItems="center">
              {/* s-product-thumbnail rather than s-image: fixed square, and it
                  draws its own placeholder when a product has no image. The
                  previous s-image used inlineSize="fill", which let the photo
                  take the whole row and squash the title and link beside it. */}
              <s-product-thumbnail
                src={product.image?.url || undefined}
                alt={product.image?.alt_text || product.title}
                size="base"
              />

              <s-text>{product.title}</s-text>
              </s-stack>

              <s-stack direction="block" gap="small-500" alignItems="end">
                <s-text type="strong">{product.price}</s-text>
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
            </s-stack>
        ))}
      </s-stack>
    </s-section>
  );
}
