import {
  getPrimaryImageUrl,
  getSelectedVariant,
  isVariantInStock,
} from "../utils/productUtils.js";

/**
 * A single recommended product, rendered to match Shopify's own cart line.
 *
 * The block sits directly beneath "Items in cart" in the order summary, so it
 * copies that row's anatomy exactly: square thumbnail, title with the variant
 * underneath, price aligned right. A cross-sell that reads as part of checkout
 * gets considered; one that reads as an advert gets distrusted and skipped, and
 * checkout is the least forgiving place to look out of place.
 *
 * `s-product-thumbnail` rather than `s-image`: it is the component Shopify's
 * cart lines use, it is always square at a fixed size, and it renders its own
 * placeholder when `src` is missing. A plain `s-box` with only padding — the
 * first attempt — collapsed to a thin grey strip instead of a square.
 *
 * What this replaced, and why:
 *   - a full-width 16:9 hero image. ~170px at order-summary width, and three
 *     cards made an ~800px wall in the column the shopper scrolls to reach
 *     "Pay now".
 *   - a variant picker per card. Asking someone to choose a size five seconds
 *     before paying costs conversions. The default in-stock variant is added
 *     and its name shown, so the choice is visible rather than hidden.
 *   - a quantity stepper. The cart lines above already do that.
 *   - a collapsible gallery. Nobody browses photos at checkout.
 *
 * No colours, radii or spacing beyond Shopify's own tokens: checkout inherits
 * the merchant's Branding API settings, so anything hardcoded here would be
 * wrong on some stores and cannot be right for all.
 */
export function ProductCard({
  product,
  index,
  selectedVariants,
  adding,
  onAddToCart,
}) {
  const isAdding = adding[product.id] || false;
  const variantId = getSelectedVariant(product, selectedVariants);
  const inStock = isVariantInStock(product, selectedVariants);

  // Shown only when it says something the title does not — "Default Title" is
  // Shopify's placeholder for a product with no options and would be noise.
  const variant = product.variants?.find((v) => v.id === variantId);
  const variantLabel =
    variant?.title && variant.title !== "Default Title" ? variant.title : null;

  return (
    // Two groups with space-between, not three children in one row.
    //
    // The price sits flush against the container edge, matching the row idiom of
    // the column this now lives in: a checkout shipping-option row puts its
    // "$5.00" there too. (It used to be justified by the cart line above it,
    // back when this rendered inside the order summary — same layout, different
    // reason, so the shape survived the move to PAYMENT1 unchanged.)
    // The first attempt gave the middle column
    // `inlineSize="fill"` to absorb the spare width, but `fill` is not a valid
    // s-box value — Box takes px, % , 0 or auto, and `fill` only exists on
    // Button and Image. The invalid value was ignored, the box never grew, and
    // the price ended up floating mid-row with dead space to its right.
    <s-stack
      direction="inline"
      gap="base"
      alignItems="center"
      justifyContent="space-between"
    >
      {/* Left group: thumbnail and text stay adjacent. */}
      <s-stack direction="inline" gap="base" alignItems="center">
        <s-product-thumbnail
          src={getPrimaryImageUrl(product, 0) || undefined}
          alt={product.title}
          size="base"
        />
        <s-stack direction="block" gap="small-500">
          <s-text>{product.title}</s-text>
          {variantLabel && (
            <s-text color="subdued" type="small">
              {variantLabel}
            </s-text>
          )}
        </s-stack>
      </s-stack>

      {/* Right group: pushed to the edge by space-between. */}
      <s-stack direction="block" gap="small-500" alignItems="end">
        <s-text type="strong">{product.price}</s-text>
        <s-button
          onClick={() => onAddToCart(variantId, product.id, index)}
          loading={isAdding}
          disabled={isAdding || !variantId || !inStock}
          variant="secondary"
        >
          {inStock ? "Add" : "Sold out"}
        </s-button>
      </s-stack>
    </s-stack>
  );
}
