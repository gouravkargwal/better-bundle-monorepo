/**
 * Phoenix Recommendations - Core Logic
 * Handles fetching and rendering recommendations
 */

// Main initialization function
function initializePhoenixRecommendations() {
  const recommendationContainer = document.querySelector('.phoenix-recommendations');
  if (!recommendationContainer) return;

  // Auto-detect context if not explicitly set
  const explicitContext = recommendationContainer.dataset.context;
  const detectedContext = window.PhoenixContextDetection.detectPageContext(recommendationContainer);
  const context = explicitContext && explicitContext !== 'auto' ? explicitContext : detectedContext;

  // Update the context in the data attribute
  recommendationContainer.dataset.context = context;

  // Update the title if it's using auto-generated text
  updateTitle(recommendationContainer, context);

  // Apply theme-specific styling
  applyThemeStyling(recommendationContainer);

  // Fetch and render recommendations
  fetchRecommendations(recommendationContainer, context);
}

// Update title based on context
function updateTitle(container, context) {
  const titleEl = container.querySelector('h3');
  if (titleEl && !titleEl.textContent.includes('{{')) {
    // If title is not using Liquid template, update it dynamically
    const title = window.PhoenixContextDetection.contextTitles[context] || 'You might also like';
    titleEl.textContent = title;
  }
}

// Apply theme-specific styling
function applyThemeStyling(container) {
  // Detect theme and apply theme-specific adjustments
  const body = document.body;
  const themeName = body.getAttribute('data-theme') ||
    body.className.match(/theme-(\w+)/)?.[1] ||
    'default';

  // Apply theme-specific CSS variables if available
  const root = document.documentElement;
  const computedStyle = getComputedStyle(root);

  // Try to inherit theme colors from various common theme CSS variables
  const primaryColor = computedStyle.getPropertyValue('--color-primary') ||
    computedStyle.getPropertyValue('--primary-color') ||
    computedStyle.getPropertyValue('--color-accent') ||
    computedStyle.getPropertyValue('--color-button') ||
    computedStyle.getPropertyValue('--color-button-text') ||
    '#2c5aa0';

  const textColor = computedStyle.getPropertyValue('--color-text') ||
    computedStyle.getPropertyValue('--text-color') ||
    computedStyle.getPropertyValue('--color-foreground') ||
    '#333';

  const bgColor = computedStyle.getPropertyValue('--color-background') ||
    computedStyle.getPropertyValue('--background-color') ||
    '#fff';

  const borderColor = computedStyle.getPropertyValue('--color-border') ||
    computedStyle.getPropertyValue('--border-color') ||
    '#e0e0e0';

  // Apply theme colors to our container
  container.style.setProperty('--phoenix-primary-color', primaryColor);
  container.style.setProperty('--phoenix-text-color', textColor);
  container.style.setProperty('--phoenix-bg-color', bgColor);
  container.style.setProperty('--phoenix-border-color', borderColor);

  // Apply theme-specific adjustments for popular themes
  if (themeName.toLowerCase().includes('dawn')) {
    container.classList.add('phoenix-theme-dawn');
  } else if (themeName.toLowerCase().includes('debut')) {
    container.classList.add('phoenix-theme-debut');
  } else if (themeName.toLowerCase().includes('brooklyn')) {
    container.classList.add('phoenix-theme-brooklyn');
  }
}

// Fetch recommendations from API
function fetchRecommendations(container, context) {
  const productId = container.dataset.productId;
  const limit = container.dataset.limit || '6';
  const layout = container.dataset.layout || 'grid';
  const columns = container.dataset.columns || 'auto';
  const showPrices = container.dataset.showPrices === 'true';
  const showReasons = container.dataset.showReasons === 'true';
  const loadingEl = container.querySelector('.recommendations-loading');
  const contentEl = container.querySelector('.recommendations-content');
  const gridEl = container.querySelector('.phoenix-recommendations-grid');
  const previewEl = container.querySelector('.phoenix-preview');

  // Hide preview and show loading state
  if (previewEl) previewEl.style.display = 'none';
  loadingEl.style.display = 'block';

  // Get current user session info
  const userId = window.Shopify?.customer?.id || null;
  const sessionId = window.Shopify?.sessionId || null;

  // Build API URL
  const apiUrl = new URL('/app/recommendations', window.location.origin);
  apiUrl.searchParams.set('context', context);
  apiUrl.searchParams.set('product_id', productId);
  if (userId) apiUrl.searchParams.set('user_id', userId);
  if (sessionId) apiUrl.searchParams.set('session_id', sessionId);
  apiUrl.searchParams.set('limit', limit);

  // Fetch recommendations
  fetch(apiUrl.toString())
    .then(response => response.json())
    .then(data => {
      loadingEl.style.display = 'none';

      // Only show widget if we have actual recommendations
      if (data.success && data.recommendations && data.recommendations.length > 0) {
        renderRecommendations(data.recommendations, gridEl, { layout, columns, showPrices, showReasons });
        contentEl.style.display = 'block';
      } else {
        // Only show preview in theme editor, not on live website
        if (previewEl && window.Shopify?.designMode) {
          previewEl.style.display = 'block';
        } else {
          // Hide the entire widget if no recommendations on live website
          container.style.display = 'none';
        }
      }
    })
    .catch(error => {
      console.error('Recommendations fetch error:', error);
      loadingEl.style.display = 'none';

      // Only show preview in theme editor on error, not on live website
      if (previewEl && window.Shopify?.designMode) {
        previewEl.style.display = 'block';
      } else {
        // Hide the entire widget on error on live website
        container.style.display = 'none';
      }
    });
}

// Render recommendations in the container
function renderRecommendations(recommendations, container, options = {}) {
  const { layout = 'grid', columns = 'auto', showPrices = true, showReasons = true } = options;

  container.innerHTML = '';

  // Apply layout-specific CSS classes and styling
  container.className = `phoenix-recommendations-grid phoenix-layout-${layout}`;

  // Set data attributes for CSS targeting
  container.setAttribute('data-columns', columns);
  container.setAttribute('data-layout', layout);

  // Handle different layout types
  if (layout === 'carousel') {
    container.style.display = 'flex';
    container.style.overflowX = 'auto';
    container.style.scrollBehavior = 'smooth';
    container.style.gap = '16px';
    container.style.paddingBottom = '10px';
    container.style.gridTemplateColumns = 'none';
  } else if (layout === 'list') {
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '12px';
    container.style.gridTemplateColumns = 'none';
  } else {
    // Grid layout
    container.style.display = 'grid';
    container.style.gap = '16px';

    if (columns !== 'auto') {
      container.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
    } else {
      // Responsive grid - let CSS handle it
      container.style.gridTemplateColumns = 'repeat(auto-fit, minmax(200px, 1fr))';
    }
  }

  recommendations.forEach(product => {
    const productEl = document.createElement('div');
    productEl.className = 'phoenix-recommendation-item';

    // Use theme's existing product card structure if available
    const existingProductCard = document.querySelector('.product-card, .product-item, .grid-product');
    if (existingProductCard) {
      // Clone theme's product card structure
      const themeCard = existingProductCard.cloneNode(true);
      themeCard.className = 'phoenix-recommendation-item';

      // Update content
      updateThemeCard(themeCard, product, showPrices, showReasons);
      container.appendChild(themeCard);
    } else {
      // Use our own structure with theme-friendly classes
      productEl.innerHTML = createProductCard(product, showPrices, showReasons);
      container.appendChild(productEl);
    }
  });
}

// Update theme card with product data
function updateThemeCard(themeCard, product, showPrices, showReasons) {
  const link = themeCard.querySelector('a') || themeCard;
  if (link.tagName === 'A') link.href = `/products/${product.handle}`;

  const img = themeCard.querySelector('img');
  if (img) {
    img.src = product.image || getDefaultImage();
    img.alt = product.imageAlt || product.title;
  }

  const title = themeCard.querySelector('h3, h4, .product-title, .product-name');
  if (title) title.textContent = product.title;

  if (showPrices) {
    const price = themeCard.querySelector('.price, .product-price, .money');
    if (price) price.textContent = `${product.currency} ${product.price}`;
  }

  // Add reason as a small badge
  if (showReasons && product.reason) {
    const reasonEl = document.createElement('span');
    reasonEl.className = 'phoenix-reason-badge';
    reasonEl.textContent = product.reason;
    reasonEl.style.cssText = 'font-size: 11px; color: #666; font-style: italic; display: block; margin-top: 4px;';
    themeCard.appendChild(reasonEl);
  }
}

// Create product card HTML
function createProductCard(product, showPrices, showReasons) {
  const priceHtml = showPrices ? `<p class="phoenix-recommendation-price">${product.currency} ${product.price}</p>` : '';
  const reasonHtml = showReasons && product.reason ? `<p class="phoenix-recommendation-reason">${product.reason}</p>` : '';

  return `
    <a href="/products/${product.handle}" class="phoenix-recommendation-link">
      <div class="phoenix-recommendation-image">
        <img src="${product.image || getDefaultImage()}" 
             alt="${product.imageAlt || product.title}" 
             loading="lazy">
      </div>
      <div class="phoenix-recommendation-info">
        <h4 class="phoenix-recommendation-title">${product.title}</h4>
        ${priceHtml}
        ${reasonHtml}
      </div>
    </a>
  `;
}

// Get default placeholder image
function getDefaultImage() {
  return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==';
}

// Export for use in other files
window.PhoenixRecommendations = {
  initializePhoenixRecommendations,
  renderRecommendations,
  fetchRecommendations
};
