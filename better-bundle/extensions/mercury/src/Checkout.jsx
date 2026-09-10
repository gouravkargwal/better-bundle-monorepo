import { render } from "preact";
import { useState, useEffect, useMemo, useRef } from "preact/hooks";
import { useRecommendations } from "./hooks/useRecommendations.js";
import { useSettledSkeleton } from "./hooks/useSettledSkeleton.js";
import { recordOfferOutcome } from "./api/analytics.js";
import { ProductCard } from "./components/ProductCard.jsx";
import { getOptionValueFromVariant } from "./utils/productUtils.js";
import { resolveSessionId } from "./utils/identity.js";
import { logger } from "./utils/logger.js";

const shopifyPlusValidated =
  shopify.instructions.value.attributes.canUpdateAttributes;

export default async () => {
  render(<Extension />, document.body);
};

function Extension() {
  const [adding, setAdding] = useState({});
  const [selectedVariants, setSelectedVariants] = useState({});
  const [addedProducts, setAddedProducts] = useState(new Set());
  const [successMessage, setSuccessMessage] = useState("");
  // One offer per checkout, taken or not.
  //
  // The recommendation request keys on the cart contents, so accepting an offer
  // changed the cart, which refetched, which produced a *new* offer — and the
  // accepted product was filtered out of the results, so there was always
  // something fresh to show. The shopper got an endless upsell treadmill on the
  // screen where they are trying to pay, and every round wrote another
  // impression row, inflating the denominator of the conversion rate the
  // merchant is billed against.
  const [hasAccepted, setHasAccepted] = useState(false);
  const hasTrackedView = useRef(false);
  const { lines, cost, buyerIdentity, storage } = shopify;
  const shopDomain = shopify.shop.myshopifyDomain;

  // Are we rendering inside the checkout editor rather than a real checkout?
  //
  // `shopify.extension.editor` is undefined on a live checkout and
  // {type: 'checkout'} in the editor. Without this check, every merchant who
  // opens the checkout customiser to position this block causes a real
  // recommendation request, which writes real `offer_impressions` rows — so
  // their own configuring shows up in their impact dashboard as offers shown
  // to shoppers who never existed, dragging the conversion rate down.
  //
  // Phoenix already avoids this via Liquid's `request.design_mode`; checkout
  // extensions have no Liquid, so it has to be read from the JS API.
  const inEditor = Boolean(shopify.extension?.editor);
  const customerId = buyerIdentity?.customer?.value?.id || null;

  // Measurement identity, read from the cart (or minted onto it once).
  //
  // Resolved before the first request rather than alongside it: an impression
  // written without it is permanently unbucketed and unattributable, and there
  // is no going back to fix the row afterwards. `undefined` means "still
  // resolving", which gates the fetch below; `null` means "resolved, and there
  // is none" — a shopper who came straight to checkout on a store that does not
  // permit attribute writes. They still get recommendations, just outside the
  // experiment.
  const [sessionId, setSessionId] = useState(undefined);
  useEffect(() => {
    if (inEditor) {
      setSessionId(null);
      return;
    }
    let cancelled = false;
    resolveSessionId(shopify).then((id) => {
      if (!cancelled) setSessionId(id);
    });
    return () => {
      cancelled = true;
    };
  }, [inEditor]);

  const cartItems = useMemo(() => {
    return (
      lines.value
        ?.map((line) => {
          const productId = line.merchandise?.product?.id;
          if (!productId) return null;
          if (productId.startsWith("gid://shopify/Product/")) {
            return productId.split("/").pop();
          }
          return productId;
        })
        .filter(Boolean) || []
    );
  }, [lines.value]);

  useEffect(() => {
    const cartProductIds = new Set(cartItems);
    setAddedProducts((prev) => {
      const newSet = new Set();
      cartProductIds.forEach((id) => newSet.add(id));
      prev.forEach((id) => {
        if (!cartProductIds.has(id)) {
          newSet.add(id);
        }
      });
      return newSet;
    });
  }, [cartItems]);

  const cartValue = useMemo(() => {
    const amount = cost.totalAmount?.value?.amount;
    return parseFloat(amount ? String(amount) : "0");
  }, [cost.totalAmount?.value?.amount]);

  const { loading, products, error } =
    useRecommendations({
      // Nothing is fetched in the editor: no request, no impression row.
      // Nothing refetched after an acceptance either — see `hasAccepted`.
      // And nothing until the identity has resolved, so the impression is
      // written with a bucketing key rather than without one.
      skip: inEditor || hasAccepted || sessionId === undefined,
      sessionId,
      context: "checkout_page",
      // One offer. Three cards made an ~800px block in the column the shopper
      // scrolls to reach "Pay now"; the server-side RETURN_LIMIT for mercury
      // is the ceiling, this is the checkout-appropriate ask.
      limit: 1,
      customerId,
      shopDomain,
      storage,
      cartItems: cartItems,
      cartValue: cartValue,
      checkoutStep: "order_summary",
    });

  const showSkeleton = useSettledSkeleton(loading);

  // No view reporting: the impression row is written server-side the moment
  // recommendations are served.


  // Auto-select default variants when products load
  useEffect(() => {
    if (products && products.length > 0) {
      products.forEach((product) => {
        if (selectedVariants[product.id]) return;

        if (product.options && product.options.length > 0) {
          const autoSelected = {};
          product.options.forEach((option) => {
            const firstAvailableVariant =
              product.variants?.find((variant) => variant.inventory > 0) ||
              product.variants?.[0];

            if (firstAvailableVariant && option.values.length > 0) {
              const optionValue = getOptionValueFromVariant(
                firstAvailableVariant,
                option.name,
                product,
              );
              autoSelected[option.name] = optionValue || option.values[0];
            } else if (option.values.length > 0) {
              autoSelected[option.name] = option.values[0];
            }
          });

          if (Object.keys(autoSelected).length > 0) {
            setSelectedVariants((prev) => {
              if (prev[product.id]) return prev;
              return {
                ...prev,
                [product.id]: autoSelected,
              };
            });
          }
        }
      });
    }
  }, [products]);

  useEffect(() => {
    if (!successMessage) return;
    const t = setTimeout(() => {
      setSuccessMessage("");
    }, 5000); // Increased to 5 seconds for better visibility
    return () => clearTimeout(t);
  }, [successMessage]);

  async function handleAddToCart(variantId, productId, position) {
    try {
      setAdding((prev) => ({ ...prev, [productId]: true }));

      if (!variantId) {
        return;
      }

      const merchandiseId = variantId.startsWith("gid://")
        ? variantId
        : `gid://shopify/ProductVariant/${variantId}`;

      // Always 1: the quantity stepper was removed from the card because the
      // cart lines directly above already let the shopper change it.
      const quantity = 1;

      // Looked up once here and reused below for the success message and the
      // outcome report. It used to be found three times, twice under the same
      // `const product` name in one block scope — a redeclaration esbuild
      // rejects, which is why this extension never bundled.
      const product = products?.find((p) => p.id === productId);
      const result = await shopify.applyCartLinesChange({
        type: "addCartLine",
        merchandiseId: merchandiseId,
        quantity: quantity,
        ...(product?.impression_id
          ? {
              attributes: [
                {
                  key: "_bb_rec_impression_id",
                  value: String(product.impression_id),
                },
              ],
            }
          : {}),
      });

      if (result.type === "success") {
        setAddedProducts((prev) => new Set([...prev, productId]));
        // Stops the cart change below from refetching a fresh offer.
        setHasAccepted(true);
        const productName = product?.title || "Product";
        setSuccessMessage(`${productName} added to cart successfully`);

        const allAddedProducts = Array.from(addedProducts);
        const productsArray = allAddedProducts.map((addedProductId) => ({
          product_id: addedProductId,
          position: position,
          quantity: quantity,
          timestamp: new Date().toISOString(),
        }));

        if (!allAddedProducts.includes(productId)) {
          productsArray.push({
            product_id: productId,
            position: position,
            quantity: quantity,
            timestamp: new Date().toISOString(),
          });
        }

        await shopify.applyMetafieldChange({
          type: "updateMetafield",
          namespace: "bb_recommendation",
          key: "extension",
          value: "mercury",
          valueType: "string",
        });

        await shopify.applyMetafieldChange({
          type: "updateMetafield",
          namespace: "bb_recommendation",
          key: "context",
          value: "checkout_page",
          valueType: "string",
        });

        await shopify.applyMetafieldChange({
          type: "updateMetafield",
          namespace: "bb_recommendation",
          key: "source",
          value: "betterbundle",
          valueType: "string",
        });

        await shopify.applyMetafieldChange({
          type: "updateMetafield",
          namespace: "bb_recommendation",
          key: "products",
          value: JSON.stringify(productsArray),
          valueType: "json_string",
        });

        // Report the acceptance. The line attribute above is the durable
        // record; this is what updates the dashboard in real time.
        if (product?.impression_id) {
          const revenue = (product.price_amount || 0) * quantity;
          recordOfferOutcome(product.impression_id, "accepted", revenue);
        }
      }
    } catch (err) {
      logger.error({
        msg: "Error adding to cart",
        error: err,
        productId: productId,
        variantId: variantId,
        position: position,
      });
    } finally {
      setAdding((prev) => ({ ...prev, [productId]: false }));
    }
  }





  if (!shopifyPlusValidated && !loading) {
    return null;
  }

  // The editor must always render something, or the merchant cannot see the
  // block to position it — Shopify's guidance is to guarantee a preview even
  // when the live conditions are not met. Static sample content, so it costs
  // no request and writes no impression.
  //
  // Same anatomy as the real card on purpose: what the merchant positions and
  // approves is exactly what a shopper will see.
  if (inEditor) {
    return (
      <s-section heading="Recommended for you">
        <s-stack direction="block" gap="base">
          <s-stack
            direction="inline"
            gap="base"
            alignItems="center"
            justifyContent="space-between"
          >
            <s-stack direction="inline" gap="base" alignItems="center">
              {/* No src: the component draws its own placeholder, which is
                  what a merchant with no recommendations yet should see. */}
              <s-product-thumbnail alt="Example product" size="base" />
              <s-stack direction="block" gap="small-500">
                <s-text>Example product</s-text>
                <s-text color="subdued" type="small">
                  Small / Black
                </s-text>
              </s-stack>
            </s-stack>
            <s-stack direction="block" gap="small-500" alignItems="end">
              <s-text type="strong">$24.99</s-text>
              <s-button variant="secondary" disabled>
                Add
              </s-button>
            </s-stack>
          </s-stack>
          <s-text color="subdued" type="small">
            Example only — shoppers see real recommendations here.
          </s-text>
        </s-stack>
      </s-section>
    );
  }

  if (loading) {
    // Nothing until the wait is long enough to need acknowledging. Checkout is
    // the most expensive place in the funnel to flash a widget that then
    // disappears, and this row disappears whenever the shop has no offer for
    // the cart. See useSettledSkeleton.
    if (!showSkeleton) {
      return null;
    }

    // Same shape as the resolved row, so the Total and "Pay now" below do not
    // shift as it resolves. The earlier skeleton mirrored the old tall card
    // and flashed ~250px before collapsing to one line.
    return (
      <s-section heading="Recommended for you">
        <s-stack
          direction="inline"
          gap="base"
          alignItems="center"
          justifyContent="space-between"
        >
          <s-stack direction="inline" gap="base" alignItems="center">
            <s-product-thumbnail size="base" alt="" />
            <s-skeleton-paragraph content="Product title"></s-skeleton-paragraph>
          </s-stack>
          <s-skeleton-paragraph content="$00.00"></s-skeleton-paragraph>
        </s-stack>
      </s-section>
    );
  }

  if (error) {
    console.error("❌ Error in useRecommendations:", error);
    return null;
  }

  const availableProducts =
    products?.filter((product) => {
      const productId = product.id;
      const numericId = productId.toString();
      const isInCart = cartItems.includes(numericId);
      const isRecentlyAdded = addedProducts.has(productId);
      return !isInCart && !isRecentlyAdded;
    }) || [];

  if (!products || products.length === 0 || availableProducts.length === 0) {
    return null;
  }

  return (
    <s-section heading="Recommended for you">
      {successMessage && (
        <s-banner
          tone="success"
          dismissible
          onDismiss={() => {
            setSuccessMessage("");
          }}
        >
          <s-text type="strong">{successMessage}</s-text>
        </s-banner>
      )}

      <s-stack direction="block" gap="base">
        {availableProducts.map((product, index) => (
          <ProductCard
            key={product.id}
            product={product}
            index={index}
            selectedVariants={selectedVariants}
            adding={adding}
            onAddToCart={handleAddToCart}
          />
        ))}
      </s-stack>
    </s-section>
  );
}
