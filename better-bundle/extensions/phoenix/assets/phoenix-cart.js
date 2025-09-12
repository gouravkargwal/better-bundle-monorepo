/**
 * Phoenix Recommendations - Cart Management
 * Handles cart operations, caching, and atomic updates
 */

// Get cached cart state to reduce API calls
async function getCachedCartState() {
  const state = getQueueState();
  const now = Date.now();

  // Return cached data if still valid
  if (state.cartCache.data && (now - state.cartCache.timestamp) < PhoenixConfig.CART_CACHE_TTL) {
    return state.cartCache.data;
  }

  // Fetch fresh cart data
  const cartResponse = await fetch('/cart.js');
  const cart = await cartResponse.json();

  // Update cache
  state.cartCache = {
    data: cart,
    timestamp: now
  };

  return cart;
}

// Invalidate cart cache (call after successful cart updates)
function invalidateCartCache() {
  const state = getQueueState();
  state.cartCache = { data: null, timestamp: 0 };
}

// Atomic cart update: add item and attribution in single operation
async function addToCartWithAttribution(productId, quantity) {
  try {
    // Step 1: Get current cart state (with caching)
    const cart = await getCachedCartState();

    // Step 2: Create attribution record
    const attribution = createAttributionData({
      productId: productId,
      pageType: getCurrentPageType(),
      sessionId: getSessionId(),
      userId: getUserId(),
      timestamp: Date.now()
    });

    // Step 3: Get existing items from cart
    const existingItems = cart.items.map(item => ({
      id: item.variant_id,
      quantity: item.quantity
    }));

    // Step 4: Merge new and existing attributes
    const existingAttributions = JSON.parse(cart.attributes?.betterbundle_attributions || '[]');
    const newAttributes = {
      ...cart.attributes, // Preserve existing attributes
      'betterbundle_attributions': JSON.stringify([...existingAttributions, attribution])
    };

    // Step 5: Construct payload for atomic update
    const payload = {
      items: [...existingItems, { id: productId, quantity: quantity }],
      attributes: newAttributes
    };

    // Step 6: Send single atomic update
    const response = await fetch('/cart/update.js', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    });

    // Step 7: Store attribution in session storage (async)
    const existingStoredAttributions = await getStoredAttributions();
    existingStoredAttributions.push(attribution);
    await storeAttributions(existingStoredAttributions);

    // Step 8: Send attribution to Atlas for backend processing
    if (window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('betterbundle:attribution:created', {
        detail: {
          ...attribution,
          eventType: 'attribution_created',
          shop_domain: window.Shopify?.shop || 'unknown'
        }
      }));
    }

    return response;

  } catch (error) {
    console.error('Atomic cart update failed:', error);
    throw error;
  }
}

// Add to cart API call (legacy - kept for compatibility)
function addToCart(productId, quantity) {
  return fetch('/cart/add.js', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      id: productId,
      quantity: quantity
    })
  });
}
