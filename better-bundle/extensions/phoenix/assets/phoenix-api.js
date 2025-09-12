// Retry mechanism with exponential backoff
async function fetchWithRetry(url, options = {}) {
  const maxAttempts = PhoenixConfig.MAX_RETRY_ATTEMPTS;
  const baseDelay = PhoenixConfig.RETRY_BACKOFF_BASE;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), PhoenixConfig.API_TIMEOUT);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      if (attempt === maxAttempts) {
        throw error;
      }

      // Exponential backoff
      const delay = baseDelay * Math.pow(2, attempt - 1);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}

// User-friendly error display
function showUserError(container, message) {
  const errorEl = document.createElement('div');
  errorEl.className = 'phoenix-error-message';
  errorEl.setAttribute('role', 'alert');
  errorEl.setAttribute('aria-live', 'polite');
  errorEl.textContent = message;

  // Style the error message
  errorEl.style.cssText = `
    padding: 12px;
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
    border-radius: 4px;
    margin: 8px 0;
    font-size: 14px;
  `;

  // Insert after loading element
  const loadingEl = container.querySelector('.recommendations-loading');
  if (loadingEl && loadingEl.parentNode) {
    loadingEl.parentNode.insertBefore(errorEl, loadingEl.nextSibling);
  }

  // Auto-remove after delay
  setTimeout(() => {
    if (errorEl.parentNode) {
      errorEl.parentNode.removeChild(errorEl);
    }
  }, PhoenixConfig.ARIA_LIVE_DELAY * 3);
}

// Fetch recommendations from API
function fetchRecommendations(container, context) {
  const productId = container.dataset.productId;
  const limit = container.dataset.limit || '6';
  const layout = container.dataset.layout || 'grid';
  const columns = container.dataset.columns || 'auto';
  const showPrices = container.dataset.showPrices === 'true';
  const showReasons = container.dataset.showReasons === 'true';
  const showAddToCart = container.dataset.showAddToCart === 'true';

  console.log('Phoenix API: Fetching recommendations with:', {
    productId,
    context,
    limit,
    layout
  });
  const contentEl = container.querySelector('.phoenix-widget-content');
  const gridEl = container.querySelector('.phoenix-widget-grid');
  // No preview element needed

  // Hide content initially (no loading state needed)
  if (contentEl) contentEl.style.display = 'none';

  // Get current user session info
  const userId = window.Shopify?.customer?.id || null;
  const sessionId = window.Shopify?.sessionId || null;

  // Build API URL with input sanitization
  // Use the public API endpoint (no authentication required)
  const appBackendUrl = 'https://anyway-prints-catalogs-collins.trycloudflare.com';
  const apiUrl = new URL('/app/api/recommendations', appBackendUrl);
  apiUrl.searchParams.set('context', SecurityUtils.sanitizeHtml(context));
  apiUrl.searchParams.set('product_id', SecurityUtils.sanitizeHtml(productId || ''));
  if (userId) apiUrl.searchParams.set('user_id', SecurityUtils.sanitizeHtml(String(userId)));
  if (sessionId) apiUrl.searchParams.set('session_id', SecurityUtils.sanitizeHtml(String(sessionId)));
  apiUrl.searchParams.set('limit', SecurityUtils.sanitizeHtml(limit));
  // Add cache-busting parameter
  apiUrl.searchParams.set('_t', Date.now().toString());

  // Fetch recommendations with retry mechanism
  fetchWithRetry(apiUrl.toString())
    .then(data => {
      console.log('🔍 Phoenix API Response:', data);

      // Validate API response structure
      if (!data || typeof data !== 'object' || !data.success) {
        console.error('❌ Invalid API response structure:', data);
        throw new Error('Invalid API response structure');
      }

      // Only show widget if we have actual recommendations
      if (data.recommendations && data.recommendations.length > 0) {
        console.log(`✅ Phoenix API: Found ${data.recommendations.length} recommendations`);

        // Sanitize all product data before rendering
        const sanitizedProducts = data.recommendations
          .map(product => SecurityUtils.sanitizeProduct(product))
          .filter(product => product !== null);

        console.log('🔍 Debug elements:', { contentEl, gridEl });
        console.log('🔍 Render options:', { layout, columns, showPrices, showReasons, showAddToCart });

        // Set the title from API response
        const titleEl = container.querySelector('.phoenix-widget-title');
        if (titleEl && data.title) {
          titleEl.textContent = data.title;
          titleEl.style.display = 'block';
        }

        if (window.renderRecommendations) {
          window.renderRecommendations(sanitizedProducts, gridEl, { layout, columns, showPrices, showReasons, showAddToCart });
        } else {
          console.error('❌ renderRecommendations function not found');
          throw new Error('renderRecommendations function not available');
        }

        if (contentEl) contentEl.style.display = 'block';
        // Show the widget container now that we have data
        container.style.display = 'block';
      } else {
        console.log('⚠️ Phoenix API: No recommendations found, hiding widget');
        // Hide the entire widget if no recommendations
        container.style.display = 'none';
      }
    })
    .catch(error => {
      console.error('Recommendations fetch error:', error);
      console.log('🔄 Phoenix API: Falling back to design mode preview...');

      // Fallback: Show design mode preview when API fails
      showDesignModePreview(container, { layout, columns, showPrices, showReasons, showAddToCart });
    });
}

// Fallback function to show design mode preview when API fails
function showDesignModePreview(container, options) {
  const { layout, columns, showPrices, showReasons, showAddToCart } = options;

  console.log('🎨 Showing design mode preview as fallback');

  const contentEl = container.querySelector('.phoenix-widget-content');
  const gridEl = container.querySelector('.phoenix-widget-grid');

  // No loading element to hide

  // Create sample products for preview
  const sampleProducts = [
    {
      id: 'sample-1',
      title: 'Sample Product 1',
      price: '$19.99',
      image: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPlByb2R1Y3QgSW1hZ2U8L3RleHQ+PC9zdmc+',
      reason: 'Recommended for you'
    },
    {
      id: 'sample-2',
      title: 'Sample Product 2',
      price: '$24.99',
      image: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPlByb2R1Y3QgSW1hZ2U8L3RleHQ+PC9zdmc+',
      reason: 'Popular choice'
    },
    {
      id: 'sample-3',
      title: 'Sample Product 3',
      price: '$29.99',
      image: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPlByb2R1Y3QgSW1hZ2U8L3RleHQ+PC9zdmc+',
      reason: 'Best seller'
    },
    {
      id: 'sample-4',
      title: 'Sample Product 4',
      price: '$34.99',
      image: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPlByb2R1Y3QgSW1hZ2U8L3RleHQ+PC9zdmc+',
      reason: 'Trending now'
    }
  ];

  // Render the sample products
  if (window.renderRecommendations) {
    window.renderRecommendations(sampleProducts, gridEl, { layout, columns, showPrices, showReasons, showAddToCart });
  }

  // Show content
  if (contentEl) contentEl.style.display = 'block';
  container.style.display = 'block';

  console.log('✅ Design mode preview displayed successfully');
}

// Export functions to global scope
window.fetchRecommendations = fetchRecommendations;
