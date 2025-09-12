/**
 * Phoenix Recommendations - Rendering Engine
 * Handles product card rendering, layout management, and theme integration
 */

// Render recommendations in the container using template-based approach
function renderRecommendations(recommendations, gridContainer, options = {}) {
  const { layout = 'grid', columns = 'auto', showPrices = true, showReasons = true, showAddToCart = true } = options;

  // Safety check for gridContainer
  if (!gridContainer) {
    console.error('Phoenix Recommendations: Grid container is null or undefined.');
    return;
  }

  // Find the main widget container to locate the template
  const widgetContainer = gridContainer.closest('.phoenix-recommendations-widget');
  if (!widgetContainer) {
    console.error('Phoenix Recommendations: Widget container not found.');
    return;
  }

  const templateNode = widgetContainer.querySelector('[data-template="phoenix-product-card"]');
  if (!templateNode) {
    console.error('Phoenix Recommendations: Product card template not found.');
    return;
  }

  gridContainer.innerHTML = ''; // Clear loading state or previous content

  // Apply layout classes to grid container
  gridContainer.className = `phoenix-widget-grid phoenix-widget-grid--${layout}`;

  // Set data attributes for CSS targeting
  gridContainer.setAttribute('data-columns', columns);
  gridContainer.setAttribute('data-layout', layout);

  // Track widget display (if analytics is available)
  if (window.PhoenixAnalytics && window.PhoenixAnalytics.trackWidgetInteraction) {
    window.PhoenixAnalytics.trackWidgetInteraction({
      action: 'widget_displayed',
      productIds: recommendations.map(r => r.id),
      pageType: window.PhoenixContextDetection ? window.PhoenixContextDetection.getCurrentPageType() : 'unknown',
      timestamp: Date.now()
    });
  }

  recommendations.forEach(product => {
    // Clone the template for each new product
    const productCard = templateNode.content.cloneNode(true).firstElementChild;

    // --- Populate the cloned template with data ---
    productCard.dataset.productId = product.id;

    const link = productCard.querySelector('.phoenix-product-link');
    if (link) link.href = `/products/${product.handle}`;

    const img = productCard.querySelector('.phoenix-main-image');
    const dotsContainer = productCard.querySelector('.phoenix-image-dots');

    if (img) {
      // Handle multiple images if available
      const images = product.images || [product.image];
      const validImages = images.filter(img => img && img.trim() !== '');

      if (validImages.length > 0) {
        img.src = validImages[0];
        img.alt = product.imageAlt || product.title;

        // Create dots for multiple images
        if (validImages.length > 1 && dotsContainer) {
          dotsContainer.innerHTML = '';
          validImages.forEach((_, index) => {
            const dot = document.createElement('div');
            dot.className = `phoenix-image-dot ${index === 0 ? 'active' : ''}`;
            dot.dataset.index = index;
            dotsContainer.appendChild(dot);
          });

          // Add carousel functionality
          setupImageCarousel(productCard, validImages);
        } else if (dotsContainer) {
          dotsContainer.innerHTML = '';
        }
      } else {
        img.src = getDefaultImage();
        img.alt = product.title;
        if (dotsContainer) dotsContainer.innerHTML = '';
      }
    }

    const title = productCard.querySelector('.phoenix-product-title');
    if (title) title.textContent = product.title;

    const price = productCard.querySelector('.phoenix-product-price');
    if (price && showPrices) {
      console.log('🔍 Price debug:', { product: product.title, price: product.price, currency: product.currency });

      // Format price with proper currency handling
      if (product.price && product.price !== '0.00') {
        const currency = product.currency || 'USD';
        const formattedPrice = parseFloat(product.price).toFixed(2);
        price.textContent = `${currency} ${formattedPrice}`;
      } else if (product.price === '0.00') {
        price.textContent = 'Free';
      } else {
        price.textContent = 'Price not available';
      }
    }

    const reason = productCard.querySelector('.phoenix-product-reason');
    if (reason && showReasons && product.reason) {
      reason.textContent = product.reason;
      reason.style.display = 'block';
    }

    // Create and append the smart "Add to Cart" button (if enabled)
    const buttonContainer = productCard.querySelector('.phoenix-product-actions');
    console.log('🔍 Button debug:', { buttonContainer, showAddToCart, productId: product.id });

    if (buttonContainer && showAddToCart) {
      const buttonHtml = createSmartAddToCartButton(product);
      console.log('🔍 Button HTML:', buttonHtml);
      buttonContainer.innerHTML = buttonHtml;
    } else if (buttonContainer && !showAddToCart) {
      buttonContainer.style.display = 'none';
    }

    // Add the populated card to the grid
    gridContainer.appendChild(productCard);
  });

  // Update add to cart buttons after rendering (if cart module is available)
  setTimeout(() => {
    if (window.PhoenixCart && window.PhoenixCart.updateAddToCartButtons) {
      window.PhoenixCart.updateAddToCartButtons(gridContainer);
    }
  }, 100);
}

// Helper function to get default image
function getDefaultImage() {
  return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==';
}

// Create smart add to cart button
function createSmartAddToCartButton(product) {
  const isInCart = window.phoenixCartItems?.includes(product.id.toString()) || false;
  const buttonText = isInCart ? 'In Cart' : 'Add to Cart';
  const buttonClass = isInCart ? 'phoenix-add-to-cart-btn phoenix-add-to-cart-btn--in-cart' : 'phoenix-add-to-cart-btn';

  return `
    <button class="${buttonClass}" 
            data-product-id="${product.id}"
            data-product-handle="${product.handle}"
            data-original-text="Add to Cart"
            ${isInCart ? 'disabled' : ''}
            onclick="handleSmartAddToCart(event)">
      <span class="phoenix-button-text">${buttonText}</span>
      <span class="phoenix-button-spinner" style="display: none;">Adding...</span>
    </button>
  `;
}

// Setup image carousel functionality
function setupImageCarousel(card, images) {
  const img = card.querySelector('.phoenix-main-image');
  const dots = card.querySelectorAll('.phoenix-image-dot');
  const prevBtn = card.querySelector('.phoenix-image-prev');
  const nextBtn = card.querySelector('.phoenix-image-next');

  let currentIndex = 0;

  function updateImage(index) {
    if (img && images[index]) {
      img.src = images[index];
      currentIndex = index;

      // Update dots
      dots.forEach((dot, i) => {
        dot.classList.toggle('active', i === index);
      });
    }
  }

  function nextImage() {
    const nextIndex = (currentIndex + 1) % images.length;
    updateImage(nextIndex);
  }

  function prevImage() {
    const prevIndex = (currentIndex - 1 + images.length) % images.length;
    updateImage(prevIndex);
  }

  // Add event listeners
  if (nextBtn) {
    nextBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      nextImage();
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      prevImage();
    });
  }

  // Add dot click listeners
  dots.forEach((dot, index) => {
    dot.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      updateImage(index);
    });
  });

  // Auto-advance every 4 seconds (optional)
  const autoAdvance = setInterval(nextImage, 4000);

  // Pause auto-advance on hover
  const carousel = card.querySelector('.phoenix-product-image-carousel');
  if (carousel) {
    carousel.addEventListener('mouseenter', () => clearInterval(autoAdvance));
    carousel.addEventListener('mouseleave', () => {
      setInterval(nextImage, 4000);
    });
  }
}

// Export functions for use in other files
window.PhoenixRenderer = {
  renderRecommendations,
  createSmartAddToCartButton,
  getDefaultImage,
  setupImageCarousel
};

// Also make renderRecommendations available globally for fallback
window.renderRecommendations = renderRecommendations;
