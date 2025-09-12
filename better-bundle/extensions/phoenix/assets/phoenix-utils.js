/**
 * Phoenix Recommendations - Utility Functions
 * Helper functions for cart integration, feedback, and common operations
 */

// Show add to cart feedback
function showAddToCartFeedback(button, type) {
  const feedback = document.createElement('div');
  // No feedback classes - just hide widget if needed
  feedback.textContent = type === 'success' ? 'Added to cart!' : 'Failed to add to cart';

  button.parentNode.appendChild(feedback);

  setTimeout(() => {
    feedback.remove();
  }, 3000);
}

// Get default placeholder image
function getDefaultImage() {
  return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==';
}

// Smart cart integration for duplicate prevention
function initializeSmartCartIntegration(container) {
  // Get current cart state
  fetch('/cart.js')
    .then(response => response.json())
    .then(cart => {
      // Store cart items for duplicate checking
      window.phoenixCartItems = cart.items.map(item => item.product_id.toString());

      // Listen for cart updates
      document.addEventListener('cart:updated', (event) => {
        window.phoenixCartItems = event.detail.items.map(item => item.product_id.toString());
        updateAddToCartButtons(container);
      });
    })
    .catch(error => {
      console.error('Failed to fetch cart:', error);
      window.phoenixCartItems = [];
    });
}

// Update add to cart buttons based on cart state
function updateAddToCartButtons(container) {
  const addToCartButtons = container.querySelectorAll('.phoenix-add-to-cart-btn');

  addToCartButtons.forEach(button => {
    const productId = button.dataset.productId;
    const isInCart = window.phoenixCartItems?.includes(productId) || false;

    if (isInCart) {
      button.textContent = 'In Cart';
      button.classList.add('in-cart');
      button.disabled = true;
    } else {
      button.textContent = 'Add to Cart';
      button.classList.remove('in-cart');
      button.disabled = false;
    }
  });
}

// Utility functions
function getCurrentPageType() {
  const container = document.querySelector('.phoenix-recommendations-widget');
  return container?.dataset.context || 'unknown';
}

function getSessionId() {
  return window.Shopify?.sessionId || 'anonymous';
}

function getUserId() {
  return window.Shopify?.customer?.id || null;
}
