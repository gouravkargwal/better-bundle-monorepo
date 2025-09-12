/**
 * Phoenix Recommendations - Main Initialization Script
 * Handles widget initialization, theme detection, and dynamic styling
 */

// Initialize Phoenix Recommendations when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
  console.log('🚀 Phoenix Recommendations: Initializing...');
  // Small delay to ensure all scripts are loaded
  setTimeout(() => {
    try {
      initializePhoenixRecommendations();
    } catch (error) {
      console.error('❌ Phoenix Recommendations: Initialization failed:', error);
    }
  }, 100);
});

// Also initialize when window loads (fallback)
window.addEventListener('load', function () {
  // Only initialize if not already done
  if (!window.PhoenixInitialized) {
    console.log('🚀 Phoenix Recommendations: Fallback initialization...');
    setTimeout(() => {
      try {
        initializePhoenixRecommendations();
      } catch (error) {
        console.error('❌ Phoenix Recommendations: Fallback initialization failed:', error);
      }
    }, 200);
  }
});

// Main initialization function
function initializePhoenixRecommendations() {
  // Prevent multiple initializations
  if (window.PhoenixInitialized) {
    console.log('🚀 Phoenix Recommendations: Already initialized, skipping...');
    return;
  }

  try {
    // Load theme overrides first
    loadThemeOverrides();

    // Find all Phoenix recommendation widgets
    const widgets = document.querySelectorAll('.phoenix-recommendations-widget');

    // Debug: Check if any elements exist with similar classes
    const allElements = document.querySelectorAll('[class*="phoenix"]');
    console.log('🔍 Debug: Found elements with "phoenix" in class:', allElements.length);

    if (widgets.length === 0) {
      console.log('📭 No Phoenix recommendation widgets found');
      console.log('🔍 Debug: Looking for elements with class containing "phoenix"...');
      allElements.forEach((el, index) => {
        console.log(`🔍 Element ${index + 1}:`, el.className, el);
      });
      window.PhoenixInitialized = true; // Mark as initialized even if no widgets
      return;
    }

    console.log(`🎯 Found ${widgets.length} Phoenix recommendation widget(s)`);

    // Initialize each widget
    widgets.forEach((widget, index) => {
      console.log(`⚙️ Initializing widget ${index + 1}/${widgets.length}`);
      initializeWidget(widget);
    });

    // Mark as initialized
    window.PhoenixInitialized = true;
    console.log('✅ Phoenix Recommendations: Initialization completed successfully');

  } catch (error) {
    console.error('❌ Phoenix Recommendations: Initialization error:', error);
    // Still mark as initialized to prevent retry loops
    window.PhoenixInitialized = true;
  }
}

// Initialize individual widget
function initializeWidget(widget) {
  try {
    // Hide design mode preview if it exists
    const previewElement = widget.querySelector('.phoenix-widget-preview');
    if (previewElement) {
      previewElement.style.display = 'none';
    }

    // Show the actual widget content
    const contentElement = widget.querySelector('.phoenix-widget-content');
    if (contentElement) {
      contentElement.style.display = 'block';
    }

    // Apply theme styling
    applyThemeStyling(widget);

    // Set up grid columns
    const gridColumns = widget.dataset.gridColumns || '4';
    const gridElement = widget.querySelector('.phoenix-widget-grid');
    if (gridElement) {
      gridElement.style.gridTemplateColumns = `repeat(${gridColumns}, 1fr)`;
    }

    // Initialize the widget (this will be handled by phoenix-api.js)
    console.log('✅ Widget initialized successfully');

    // Fetch recommendations from API
    if (window.fetchRecommendations) {
      console.log('🚀 Calling fetchRecommendations...');
      window.fetchRecommendations(widget, 'auto');
    } else {
      console.error('❌ fetchRecommendations function not found');
    }

  } catch (error) {
    console.error('❌ Error initializing widget:', error);
  }
}

// Load theme-specific overrides
function loadThemeOverrides() {
  // Detect current theme
  const detectedTheme = detectCurrentTheme();
  console.log('🎨 Detected theme:', detectedTheme);

  // Get theme overrides from global variable (set by Liquid template)
  const themeOverrides = window.PhoenixThemeOverrides || {};

  // Load override file if available
  const overrideUrl = themeOverrides[detectedTheme];
  if (overrideUrl) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = overrideUrl;
    link.onload = () => console.log(`🎨 Loaded theme override: ${detectedTheme}`);
    link.onerror = () => console.log(`⚠️ Theme override not found: ${detectedTheme}`);
    document.head.appendChild(link);
  } else {
    console.log('🎨 No specific theme override found, using default styles');
  }
}

// Detect current theme using multiple methods
function detectCurrentTheme() {
  const body = document.body;
  const html = document.documentElement;

  // Method 1: Check Shopify theme object
  if (window.Shopify?.theme?.name) {
    return window.Shopify.theme.name.toLowerCase();
  }

  // Method 2: Check data attributes
  let themeName = body.getAttribute('data-theme') ||
    html.getAttribute('data-theme') ||
    body.getAttribute('data-template') ||
    body.getAttribute('data-shopify-theme') ||
    html.getAttribute('data-shopify-theme');

  if (themeName) {
    return themeName.toLowerCase();
  }

  // Method 3: Check meta tags
  const themeMeta = document.querySelector('meta[name="shopify-theme"]') ||
    document.querySelector('meta[name="theme"]') ||
    document.querySelector('meta[property="shopify:theme"]');

  if (themeMeta) {
    return themeMeta.getAttribute('content').toLowerCase();
  }

  // Method 4: Check class names
  const themeClass = Array.from(body.classList).find(cls =>
    cls.includes('dawn') || cls.includes('debut') || cls.includes('brooklyn') ||
    cls.includes('oslo') || cls.includes('craft') || cls.includes('narrative') ||
    cls.includes('venture') || cls.includes('supply') || cls.includes('express') ||
    cls.includes('minimal') || cls.includes('simple')
  );

  if (themeClass) {
    return themeClass.toLowerCase();
  }

  // Method 5: Check CSS variables
  const computedStyle = getComputedStyle(document.documentElement);
  const cssVars = Array.from(computedStyle).filter(prop => prop.startsWith('--'));

  for (const theme of ['dawn', 'debut', 'brooklyn', 'oslo', 'craft', 'narrative', 'venture', 'supply', 'express', 'minimal', 'simple']) {
    if (cssVars.some(prop => prop.includes(theme))) {
      return theme;
    }
  }

  return 'unknown';
}

// Apply theme-specific styling
function applyThemeStyling(container) {
  // Check if auto theme colors is enabled
  const autoThemeColors = container.dataset.autoThemeColors === 'true';

  if (autoThemeColors) {
    // Apply Polaris integration for theme colors
    const detectedTheme = detectCurrentTheme();
    if (window.PhoenixPolarisIntegration) {
      window.PhoenixPolarisIntegration.init();
    }

    // Then apply dynamic theme variables (this will override defaults with actual theme colors)
    applyThemeVariables(container);
  }

  // Apply grid columns setting
  const gridColumns = container.dataset.gridColumns || '4';
  container.style.setProperty('--phx-grid-columns', gridColumns);

  console.log('🎨 Applied theme styling with auto-colors:', autoThemeColors, 'grid-columns:', gridColumns);
}

// Apply dynamic theme variables
function applyThemeVariables(widgetElement) {
  const rootStyle = getComputedStyle(document.documentElement);
  const bodyStyle = getComputedStyle(document.body);

  // Map widget variables to theme variables with fallbacks
  const variableMap = {
    '--phx-button-background': [
      '--color-button', '--color-primary', '--color-accent', '--button-background',
      '--primary-color', '--accent-color', '--color-button-background'
    ],
    '--phx-button-color': [
      '--color-button-text', '--color-primary-text', '--button-color',
      '--primary-text-color', '--color-button-text'
    ],
    '--phx-button-hover': [
      '--color-button-hover', '--color-primary-hover', '--button-hover',
      '--primary-hover-color', '--color-button-hover'
    ],
    '--phx-text-color': [
      '--color-text', '--color-body-text', '--text-color',
      '--body-text-color', '--color-text-primary'
    ],
    '--phx-title-color': [
      '--color-heading', '--color-title', '--heading-color',
      '--title-color', '--color-heading-primary'
    ],
    '--phx-border-color': [
      '--color-border', '--color-border-light', '--border-color',
      '--color-border-primary'
    ],
    '--phx-background-color': [
      '--color-background', '--color-background-secondary', '--background-color',
      '--color-background-primary'
    ],
    '--phx-accent-color': [
      '--color-accent', '--color-primary', '--accent-color',
      '--primary-color', '--color-accent-primary'
    ],
    '--phx-price-color': [
      '--color-price', '--color-accent', '--color-primary', '--price-color',
      '--accent-color', '--primary-color'
    ]
  };

  // Apply each variable
  for (const [widgetVar, themeVars] of Object.entries(variableMap)) {
    let foundValue = null;

    // Try to find value from theme variables
    for (const themeVar of themeVars) {
      const value = rootStyle.getPropertyValue(themeVar).trim() ||
        bodyStyle.getPropertyValue(themeVar).trim();

      if (value && value !== 'initial' && value !== 'inherit' && value !== 'transparent') {
        foundValue = value;
        break;
      }
    }

    // Apply the found value or keep existing
    if (foundValue) {
      widgetElement.style.setProperty(widgetVar, foundValue);
    }
  }

  console.log('🎨 Applied theme variables to Phoenix widget');
}

// Export functions for use by other scripts
window.PhoenixMain = {
  initializePhoenixRecommendations,
  initializeWidget,
  detectCurrentTheme,
  applyThemeStyling,
  applyThemeVariables
};