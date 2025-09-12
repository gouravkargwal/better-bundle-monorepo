/**
 * Phoenix Polaris Integration - "Good Guest" Approach
 * Inherits core theme styles (fonts, colors) but maintains professional Polaris-like components
 */

window.PhoenixPolarisIntegration = {
  // Initialize the Polaris-inspired integration
  init() {
    this.inheritCoreThemeStyles();
    this.applyPolarisDesignSystem();
    this.protectComponentsFromTheme();
    this.ensureConsistentExperience();
  },

  // Inherit only the core theme styles (fonts, colors, spacing)
  inheritCoreThemeStyles() {
    const widgets = document.querySelectorAll('.phoenix-recommendations-widget');

    widgets.forEach(widget => {
      // Get theme's core styles
      const themeCore = this.extractThemeCore();

      // Apply only core inheritance
      widget.style.setProperty('--phx-theme-font-family', themeCore.fontFamily);
      widget.style.setProperty('--phx-theme-text-color', themeCore.textColor);
      widget.style.setProperty('--phx-theme-background-color', themeCore.backgroundColor);
      widget.style.setProperty('--phx-theme-primary-color', themeCore.primaryColor);
      widget.style.setProperty('--phx-theme-border-color', themeCore.borderColor);

      // Apply to widget container
      widget.style.fontFamily = themeCore.fontFamily;
      widget.style.color = themeCore.textColor;
    });
  },

  // Extract only the core theme styles we want to inherit
  extractThemeCore() {
    const body = document.body;
    const computedStyle = getComputedStyle(body);

    return {
      fontFamily: computedStyle.fontFamily,
      textColor: computedStyle.color,
      backgroundColor: computedStyle.backgroundColor,
      primaryColor: this.findPrimaryColor(),
      borderColor: this.findBorderColor()
    };
  },

  // Find theme's primary color
  findPrimaryColor() {
    // Look for primary color in CSS custom properties
    const root = getComputedStyle(document.documentElement);
    const primaryVars = [
      '--color-primary',
      '--color-accent',
      '--color-button',
      '--color-scheme-1',
      '--color-scheme-2'
    ];

    for (const varName of primaryVars) {
      const value = root.getPropertyValue(varName).trim();
      if (value && value !== 'rgba(0, 0, 0, 0)' && value !== 'transparent') {
        return value;
      }
    }

    // Fallback: look for primary color in buttons
    const buttons = document.querySelectorAll('button, .btn, .button');
    if (buttons.length > 0) {
      const buttonStyle = getComputedStyle(buttons[0]);
      return buttonStyle.backgroundColor;
    }

    return '#2c5aa0'; // Default Shopify blue
  },

  // Find theme's border color
  findBorderColor() {
    const root = getComputedStyle(document.documentElement);
    const borderVars = [
      '--color-border',
      '--border-color',
      '--color-divider'
    ];

    for (const varName of borderVars) {
      const value = root.getPropertyValue(varName).trim();
      if (value && value !== 'rgba(0, 0, 0, 0)' && value !== 'transparent') {
        return value;
      }
    }

    return '#e0e0e0'; // Default light gray
  },

  // Apply Polaris-inspired design system
  applyPolarisDesignSystem() {
    const widgets = document.querySelectorAll('.phoenix-recommendations-widget');

    widgets.forEach(widget => {
      // Add Polaris-inspired class
      widget.classList.add('phoenix-polaris');

      // Apply Polaris design tokens
      this.applyPolarisTokens(widget);

      // Style components with Polaris approach
      this.stylePolarisComponents(widget);
    });
  },

  // Apply Polaris design tokens
  applyPolarisTokens(widget) {
    // Polaris-inspired color palette
    const polarisColors = {
      '--phx-polaris-primary': '#2c5aa0',
      '--phx-polaris-primary-hover': '#1e3f73',
      '--phx-polaris-primary-pressed': '#153a5e',
      '--phx-polaris-surface': '#ffffff',
      '--phx-polaris-surface-hover': '#f6f6f7',
      '--phx-polaris-border': '#d1d5db',
      '--phx-polaris-border-hover': '#9ca3af',
      '--phx-polaris-text': '#374151',
      '--phx-polaris-text-secondary': '#6b7280',
      '--phx-polaris-text-disabled': '#9ca3af',
      '--phx-polaris-shadow': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
      '--phx-polaris-shadow-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      '--phx-polaris-radius': '6px',
      '--phx-polaris-radius-large': '8px',
      '--phx-polaris-spacing-xs': '4px',
      '--phx-polaris-spacing-sm': '8px',
      '--phx-polaris-spacing-md': '12px',
      '--phx-polaris-spacing-lg': '16px',
      '--phx-polaris-spacing-xl': '20px',
      '--phx-polaris-spacing-2xl': '24px'
    };

    // Apply tokens to widget
    Object.entries(polarisColors).forEach(([property, value]) => {
      widget.style.setProperty(property, value);
    });
  },

  // Style components with Polaris approach
  stylePolarisComponents(widget) {
    // Style buttons with Polaris design
    const buttons = widget.querySelectorAll('.phoenix-add-to-cart-btn');
    buttons.forEach(button => {
      this.applyPolarisButton(button);
    });

    // Style product cards with Polaris design
    const cards = widget.querySelectorAll('.phoenix-product-card');
    cards.forEach(card => {
      this.applyPolarisCard(card);
    });

    // Style titles with Polaris typography
    const titles = widget.querySelectorAll('.phoenix-widget-title');
    titles.forEach(title => {
      this.applyPolarisTypography(title);
    });
  },

  // Apply Polaris button styling
  applyPolarisButton(button) {
    // Reset any theme interference
    button.style.all = 'unset';

    // Apply Polaris button styles
    button.style.display = 'inline-flex';
    button.style.alignItems = 'center';
    button.style.justifyContent = 'center';
    button.style.padding = 'var(--phx-polaris-spacing-sm) var(--phx-polaris-spacing-lg)';
    button.style.fontSize = '14px';
    button.style.fontWeight = '500';
    button.style.lineHeight = '1.5';
    button.style.borderRadius = 'var(--phx-polaris-radius)';
    button.style.border = '1px solid var(--phx-polaris-primary)';
    button.style.backgroundColor = 'var(--phx-polaris-primary)';
    button.style.color = '#ffffff';
    button.style.cursor = 'pointer';
    button.style.transition = 'all 0.15s ease-in-out';
    button.style.boxShadow = 'var(--phx-polaris-shadow)';
    button.style.fontFamily = 'var(--phx-theme-font-family, inherit)';
    button.style.textDecoration = 'none';
    button.style.outline = 'none';
    button.style.width = '100%';
    button.style.boxSizing = 'border-box';

    // Add hover effects
    button.addEventListener('mouseenter', () => {
      button.style.backgroundColor = 'var(--phx-polaris-primary-hover)';
      button.style.boxShadow = 'var(--phx-polaris-shadow-hover)';
      button.style.transform = 'translateY(-1px)';
    });

    button.addEventListener('mouseleave', () => {
      button.style.backgroundColor = 'var(--phx-polaris-primary)';
      button.style.boxShadow = 'var(--phx-polaris-shadow)';
      button.style.transform = 'translateY(0)';
    });

    button.addEventListener('mousedown', () => {
      button.style.backgroundColor = 'var(--phx-polaris-primary-pressed)';
      button.style.transform = 'translateY(0)';
    });

    button.addEventListener('mouseup', () => {
      button.style.backgroundColor = 'var(--phx-polaris-primary-hover)';
    });
  },

  // Apply Polaris card styling
  applyPolarisCard(card) {
    // Reset any theme interference
    card.style.border = 'none';
    card.style.boxShadow = 'none';
    card.style.background = 'none';

    // Apply Polaris card styles
    card.style.backgroundColor = 'var(--phx-polaris-surface)';
    card.style.border = '1px solid var(--phx-polaris-border)';
    card.style.borderRadius = 'var(--phx-polaris-radius-large)';
    card.style.boxShadow = 'var(--phx-polaris-shadow)';
    card.style.overflow = 'hidden';
    card.style.transition = 'all 0.15s ease-in-out';
    card.style.position = 'relative';

    // Add hover effects
    card.addEventListener('mouseenter', () => {
      card.style.boxShadow = 'var(--phx-polaris-shadow-hover)';
      card.style.transform = 'translateY(-2px)';
      card.style.borderColor = 'var(--phx-polaris-border-hover)';
    });

    card.addEventListener('mouseleave', () => {
      card.style.boxShadow = 'var(--phx-polaris-shadow)';
      card.style.transform = 'translateY(0)';
      card.style.borderColor = 'var(--phx-polaris-border)';
    });
  },

  // Apply Polaris typography
  applyPolarisTypography(title) {
    title.style.fontSize = '20px';
    title.style.fontWeight = '600';
    title.style.lineHeight = '1.4';
    title.style.color = 'var(--phx-polaris-text)';
    title.style.margin = '0 0 var(--phx-polaris-spacing-lg) 0';
    title.style.fontFamily = 'var(--phx-theme-font-family, inherit)';
  },

  // Protect components from theme interference
  protectComponentsFromTheme() {
    const widgets = document.querySelectorAll('.phoenix-polaris');

    widgets.forEach(widget => {
      // Add CSS isolation
      widget.style.isolation = 'isolate';

      // Protect buttons from theme styles
      const buttons = widget.querySelectorAll('.phoenix-add-to-cart-btn');
      buttons.forEach(button => {
        button.style.all = 'unset';
        button.classList.add('phoenix-polaris-button');
      });

      // Protect cards from theme styles
      const cards = widget.querySelectorAll('.phoenix-product-card');
      cards.forEach(card => {
        card.classList.add('phoenix-polaris-card');
      });
    });
  },

  // Ensure consistent experience across all themes
  ensureConsistentExperience() {
    // Add global Polaris styles
    this.injectPolarisStyles();

    // Ensure proper z-index
    const widgets = document.querySelectorAll('.phoenix-polaris');
    widgets.forEach((widget, index) => {
      widget.style.zIndex = '1';
    });
  },

  // Inject global Polaris styles
  injectPolarisStyles() {
    if (document.getElementById('phoenix-polaris-styles')) return;

    const style = document.createElement('style');
    style.id = 'phoenix-polaris-styles';
    style.textContent = `
      .phoenix-polaris-button {
        all: unset !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-family: var(--phx-theme-font-family, inherit) !important;
      }
      
      .phoenix-polaris-card {
        background-color: var(--phx-polaris-surface) !important;
        border: 1px solid var(--phx-polaris-border) !important;
        border-radius: var(--phx-polaris-radius-large) !important;
        box-shadow: var(--phx-polaris-shadow) !important;
      }
      
      .phoenix-polaris .phoenix-widget-title {
        font-family: var(--phx-theme-font-family, inherit) !important;
        color: var(--phx-polaris-text) !important;
      }
      
      .phoenix-polaris .phoenix-product-title {
        font-family: var(--phx-theme-font-family, inherit) !important;
        color: var(--phx-polaris-text) !important;
      }
      
      .phoenix-polaris .phoenix-product-price {
        font-family: var(--phx-theme-font-family, inherit) !important;
        color: var(--phx-polaris-text-secondary) !important;
      }
    `;

    document.head.appendChild(style);
  },

  // Re-initialize when new widgets are added
  reinitialize() {
    setTimeout(() => {
      this.init();
    }, 100);
  }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.PhoenixPolarisIntegration.init();
});

// Re-initialize on AJAX events
document.addEventListener('shopify:section:load', () => {
  window.PhoenixPolarisIntegration.reinitialize();
});

document.addEventListener('shopify:section:reorder', () => {
  window.PhoenixPolarisIntegration.reinitialize();
});
