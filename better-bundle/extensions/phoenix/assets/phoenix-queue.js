/**
 * Phoenix Recommendations - Queue Management
 * High-volume traffic management with request queuing and rate limiting
 */

// Queue management using configuration namespace
function getQueueState() {
  return window.PhoenixRecommendations?.state || {
    requestQueue: new Map(),
    requestInProgress: new Set(),
    queueProcessor: null,
    cartCache: { data: null, timestamp: 0 },
    analyticsQueue: []
  };
}

// Queue cart update for high-volume traffic management
function queueCartUpdate(productId, quantity, button) {
  const state = getQueueState();

  // Check queue size limit
  if (state.requestQueue.size >= PhoenixConfig.MAX_QUEUE_SIZE) {
    console.warn('Queue size limit reached, rejecting request for product:', productId);
    showUserError(button.closest('.phoenix-recommendations-widget'), 'Too many requests. Please wait a moment.');
    return;
  }

  // Mark request as in progress
  state.requestInProgress.add(productId);

  // Add to queue
  state.requestQueue.set(productId, {
    productId,
    quantity,
    button,
    timestamp: Date.now()
  });

  // Process queue if not already running
  if (!state.queueProcessor) {
    processCartUpdateQueue();
  }
}

// Process cart update queue with rate limiting
async function processCartUpdateQueue() {
  const state = getQueueState();
  state.queueProcessor = true;

  while (state.requestQueue.size > 0) {
    const [productId, request] = state.requestQueue.entries().next().value;
    state.requestQueue.delete(productId);

    try {
      await processCartUpdate(request);
    } catch (error) {
      console.error('Cart update failed for product:', productId, error);
      handleCartUpdateError(request, error);
    }

    // Rate limiting: configurable delay between requests
    await new Promise(resolve => setTimeout(resolve, PhoenixConfig.RATE_LIMIT_DELAY));
  }

  state.queueProcessor = null;
}

// Process individual cart update
async function processCartUpdate(request) {
  const { productId, quantity, button } = request;

  try {
    const response = await addToCartWithAttribution(productId, quantity);

    if (response.ok) {
      // Update cart state
      window.phoenixCartItems = window.phoenixCartItems || [];
      window.phoenixCartItems.push(productId);

      // Update button state
      button.textContent = 'In Cart';
      button.classList.add('in-cart');
      button.disabled = true;

      // Track successful addition
      trackWidgetInteraction({
        action: 'add_to_cart_success',
        productId: productId,
        pageType: getCurrentPageType(),
        timestamp: Date.now()
      });

      // Show success feedback
      showAddToCartFeedback(button, 'success');

      // Trigger cart update event
      document.dispatchEvent(new CustomEvent('cart:updated', {
        detail: { items: window.phoenixCartItems }
      }));

      // Invalidate cart cache after successful update
      invalidateCartCache();

      console.log('Item and attribution added atomically');

    } else {
      throw new Error('Failed to add to cart');
    }

  } finally {
    // Remove from in-progress set
    state.requestInProgress.delete(productId);
  }
}

// Handle cart update errors
function handleCartUpdateError(request, error) {
  const { productId, button } = request;
  const state = getQueueState();

  // Reset button state
  button.disabled = false;
  button.querySelector('.button-text').style.display = 'inline';
  button.querySelector('.loading-spinner').style.display = 'none';

  // Track failed addition
  trackWidgetInteraction({
    action: 'add_to_cart_failed',
    productId: productId,
    pageType: getCurrentPageType(),
    timestamp: Date.now(),
    error: error.message
  });

  // Show error feedback
  showAddToCartFeedback(button, 'error');

  // Remove from in-progress set
  state.requestInProgress.delete(productId);
}

// Smart add to cart handler with high-volume optimizations
function handleSmartAddToCart(event) {
  event.preventDefault();
  event.stopPropagation();

  const button = event.currentTarget;
  const productId = button.dataset.productId;
  const productHandle = button.dataset.productHandle;

  // Check if already in cart
  if (window.phoenixCartItems?.includes(productId)) {
    return;
  }

  // Check if request is already in progress for this product
  const state = getQueueState();
  if (state.requestInProgress.has(productId)) {
    console.log('Request already in progress for product:', productId);
    return;
  }

  // Show loading state
  button.disabled = true;
  button.querySelector('.button-text').style.display = 'none';
  button.querySelector('.loading-spinner').style.display = 'inline';

  // Track widget interaction
  trackWidgetInteraction({
    action: 'add_to_cart_clicked',
    productId: productId,
    pageType: getCurrentPageType(),
    timestamp: Date.now()
  });

  // Queue the request for high-volume traffic management
  queueCartUpdate(productId, 1, button);
}
