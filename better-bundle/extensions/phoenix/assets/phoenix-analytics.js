/**
 * Phoenix Recommendations - Analytics & Attribution
 * Handles widget interaction tracking, analytics queuing, and attribution management
 */

// Track widget interactions
function trackWidgetInteraction(data) {
  const eventData = {
    ...data,
    sessionId: getSessionId(),
    userId: getUserId(),
    timestamp: Date.now()
  };

  // Try to send to Atlas web pixel
  try {
    if (window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('betterbundle:widget:interaction', {
        detail: eventData
      }));
    }
  } catch (error) {
    console.warn('Failed to dispatch analytics event, queuing for retry:', error);
    // Queue event for retry if dispatch fails
    queueAnalyticsEvent('betterbundle:widget:interaction', eventData);
  }
}

// Queue analytics events for retry
function queueAnalyticsEvent(eventType, data) {
  const state = getQueueState();
  state.analyticsQueue.push({
    eventType,
    data,
    timestamp: Date.now(),
    attempts: 0
  });

  // Process queue if not already running
  if (!state.analyticsProcessor) {
    processAnalyticsQueue();
  }
}

// Process analytics queue with retry logic
async function processAnalyticsQueue() {
  const state = getQueueState();
  state.analyticsProcessor = true;

  while (state.analyticsQueue.length > 0) {
    const event = state.analyticsQueue.shift();

    try {
      if (window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent(event.eventType, {
          detail: event.data
        }));
      }
    } catch (error) {
      event.attempts++;

      // Retry up to 3 times
      if (event.attempts < 3) {
        state.analyticsQueue.push(event);
        await new Promise(resolve => setTimeout(resolve, 1000 * event.attempts));
      } else {
        console.error('Failed to process analytics event after 3 attempts:', event);
      }
    }
  }

  state.analyticsProcessor = null;
}

// Create attribution data object (used by atomic cart update)
function createAttributionData(data) {
  // Generate unique attribution ID
  const attributionId = 'attr_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

  // Create attribution object
  return {
    id: attributionId,
    productId: data.productId,
    pageType: data.pageType,
    sessionId: data.sessionId,
    userId: data.userId,
    timestamp: data.timestamp,
    status: 'pending',
    expiresAt: Date.now() + (PhoenixConfig.ATTRIBUTION_EXPIRY_DAYS * 24 * 60 * 60 * 1000)
  };
}

// Get stored attributions from session storage (async for high-volume)
async function getStoredAttributions() {
  return new Promise((resolve) => {
    try {
      // Use setTimeout to make it non-blocking
      setTimeout(() => {
        const stored = sessionStorage.getItem('betterbundle_attributions');
        resolve(stored ? JSON.parse(stored) : []);
      }, 0);
    } catch (error) {
      console.error('Failed to parse stored attributions:', error);
      resolve([]);
    }
  });
}

// Store attributions in session storage (async for high-volume)
async function storeAttributions(attributions) {
  return new Promise((resolve) => {
    try {
      // Use setTimeout to make it non-blocking
      setTimeout(() => {
        sessionStorage.setItem('betterbundle_attributions', JSON.stringify(attributions));
        resolve();
      }, 0);
    } catch (error) {
      console.error('Failed to store attributions:', error);
      resolve();
    }
  });
}

// Attach attribution to cart for revenue tracking
function attachAttributionToCart(attribution) {
  // Add attribution to cart attributes
  return fetch('/cart/update.js', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      attributes: {
        'betterbundle_attribution': JSON.stringify(attribution)
      }
    })
  }).then(response => {
    if (!response.ok) {
      throw new Error('Failed to attach attribution to cart');
    }
    return response;
  }).catch(error => {
    console.error('Failed to attach attribution to cart:', error);
    throw error;
  });
}
