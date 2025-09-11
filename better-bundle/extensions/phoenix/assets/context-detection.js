/**
 * Phoenix Recommendations - Context Detection
 * Enhanced context detection for Shopify theme extensions
 */

// Enhanced context detection function
function detectPageContext(container) {
  // Check for cached context first
  const cacheKey = 'phoenix_context_' + window.location.pathname;
  const cachedContext = sessionStorage.getItem(cacheKey);
  if (cachedContext) {
    return cachedContext;
  }

  // Get Shopify Liquid context data
  const template = container?.dataset.template || '';
  const pageType = container?.dataset.pageType || '';
  const locale = container?.dataset.locale || 'en';
  const theme = container?.dataset.theme || '';

  const path = window.location.pathname;
  const search = window.location.search;
  const hash = window.location.hash;

  // Remove locale prefix from path for detection
  const localePrefix = new RegExp(`^/${locale}/`);
  const cleanPath = path.replace(localePrefix, '/');

  // 1. Use Shopify's page_type if available (most reliable)
  if (pageType) {
    const contextMap = {
      'product': 'product_page',
      'collection': 'collection',
      'index': 'homepage',
      'cart': 'cart',
      'search': 'search',
      'blog': 'blog',
      'article': 'blog',
      'page': 'homepage', // Custom pages default to homepage context
      '404': 'not_found'
    };

    if (contextMap[pageType]) {
      const context = contextMap[pageType];
      sessionStorage.setItem(cacheKey, context);
      return context;
    }
  }

  // 2. Use Shopify's template if available
  if (template) {
    const templateMap = {
      'product': 'product_page',
      'collection': 'collection',
      'index': 'homepage',
      'cart': 'cart',
      'search': 'search',
      'blog': 'blog',
      'article': 'blog',
      'page': 'homepage',
      '404': 'not_found'
    };

    if (templateMap[template]) {
      const context = templateMap[template];
      sessionStorage.setItem(cacheKey, context);
      return context;
    }
  }

  // 3. Fallback to URL-based detection with improved patterns

  // Product page - handle localized URLs
  if (cleanPath.match(/^\/products\/[^\/]+/) || path.match(/^\/[a-z]{2}\/products\/[^\/]+/)) {
    const context = 'product_page';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Cart page - handle various cart URLs
  if (cleanPath === '/cart' || cleanPath === '/cart/' || path.includes('/cart')) {
    const context = 'cart';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Homepage - handle localized root
  if (cleanPath === '/' || cleanPath === '/index' || path === '/' || path === '/index') {
    const context = 'homepage';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Collection page - handle localized URLs
  if (cleanPath.match(/^\/collections\/[^\/]+/) || path.match(/^\/[a-z]{2}\/collections\/[^\/]+/)) {
    const context = 'collection';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Search results - improved detection
  if (search.includes('q=') || search.includes('query=') || search.includes('search=') ||
    cleanPath.includes('/search') || path.includes('/search')) {
    const context = 'search';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Blog post - handle localized URLs
  if (cleanPath.match(/^\/blogs\/[^\/]+/) || path.match(/^\/[a-z]{2}\/blogs\/[^\/]+/)) {
    const context = 'blog';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Checkout - handle modern checkout URLs
  if (cleanPath.includes('/checkout') || cleanPath.includes('/checkouts/') ||
    path.includes('/checkout') || path.includes('/checkouts/') ||
    window.Shopify?.Checkout) {
    const context = 'checkout';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Customer account - handle localized URLs
  if (cleanPath.match(/^\/account/) || path.match(/^\/[a-z]{2}\/account/)) {
    const context = 'account';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // 404 page - improved detection
  if (cleanPath.includes('/404') || document.title.includes('404') ||
    document.title.includes('Not Found') || document.title.includes('Page Not Found')) {
    const context = 'not_found';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // 4. Check custom contexts from widget configuration
  // This would be loaded from the widget config API if needed
  // For now, we'll check some common custom patterns
  const customContexts = [
    { pattern: /^\/custom-page/, context: 'homepage' },
    { pattern: /^\/special-offer/, context: 'product_page' },
    { pattern: /^\/landing/, context: 'homepage' }
  ];

  for (const custom of customContexts) {
    if (custom.pattern.test(cleanPath)) {
      const context = custom.context;
      sessionStorage.setItem(cacheKey, context);
      return context;
    }
  }

  // 5. Theme-specific detection
  const body = document.body;
  const themeClasses = body.className;

  // Check for theme-specific page indicators
  if (themeClasses.includes('template-product')) {
    const context = 'product_page';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }
  if (themeClasses.includes('template-collection')) {
    const context = 'collection';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }
  if (themeClasses.includes('template-index')) {
    const context = 'homepage';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }
  if (themeClasses.includes('template-cart')) {
    const context = 'cart';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }
  if (themeClasses.includes('template-search')) {
    const context = 'search';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }
  if (themeClasses.includes('template-blog') || themeClasses.includes('template-article')) {
    const context = 'blog';
    sessionStorage.setItem(cacheKey, context);
    return context;
  }

  // Log unexpected context for debugging
  const fallbackContext = 'product_page';
  console.warn('Phoenix Recommendations: Unexpected page context detected', {
    path: cleanPath,
    template: template,
    pageType: pageType,
    theme: theme,
    fallback: fallbackContext
  });

  // Send debug info to backend (if analytics enabled)
  if (window.Shopify?.analytics) {
    try {
      fetch('/app/api/widget-config/debug', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: cleanPath,
          template: template,
          pageType: pageType,
          theme: theme,
          userAgent: navigator.userAgent,
          timestamp: new Date().toISOString()
        })
      }).catch(() => { }); // Silent fail for debug endpoint
    } catch (e) {
      // Silent fail
    }
  }

  sessionStorage.setItem(cacheKey, fallbackContext);
  return fallbackContext;
}

// Context title mapping
const contextTitles = {
  'product_page': 'Customers who viewed this also bought',
  'homepage': 'Popular products',
  'cart': 'Frequently bought together',
  'collection': 'Similar products',
  'search': 'You might also like',
  'blog': 'Featured products',
  'checkout': 'Last chance to add',
  'account': 'Recommended for you',
  'not_found': 'Popular products'
};

// Export for use in other files
window.PhoenixContextDetection = {
  detectPageContext,
  contextTitles
};
