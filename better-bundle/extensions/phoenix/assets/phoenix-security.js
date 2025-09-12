/**
 * Phoenix Recommendations - Security Utilities
 * XSS protection, input sanitization, and safe DOM manipulation
 */

// Security utilities for XSS protection
const SecurityUtils = {
  // Simple HTML sanitization (for basic XSS protection)
  sanitizeHtml: function (unsafe) {
    if (typeof unsafe !== 'string') return '';

    return unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  // Validate and sanitize product data
  sanitizeProduct: function (product) {
    if (!product || typeof product !== 'object') return null;

    return {
      id: this.sanitizeHtml(String(product.id || '')),
      title: this.sanitizeHtml(String(product.title || '')),
      handle: this.sanitizeHtml(String(product.handle || '')),
      price: this.sanitizeHtml(String(product.price || '')),
      compare_at_price: this.sanitizeHtml(String(product.compare_at_price || '')),
      image: this.sanitizeHtml(String(product.image || '')),
      reason: this.sanitizeHtml(String(product.reason || ''))
    };
  },

  // Validate API response structure
  validateApiResponse: function (data) {
    if (!data || typeof data !== 'object') return false;
    if (!Array.isArray(data.products)) return false;

    return data.products.every(product =>
      product &&
      typeof product.id !== 'undefined' &&
      typeof product.title === 'string'
    );
  }
};