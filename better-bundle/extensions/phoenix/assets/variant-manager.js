/**
 * VariantManager - Handles variant matching, pricing, and availability
 * Optimized for performance with caching and minimal DOM queries
 */
class VariantManager {
  constructor() {
    this.variantCache = new Map(); // Cache variant matching results
    this.optionCache = new Map(); // Cache option positions
  }

  // Get option position with caching
  getOptionPosition(optionName, options) {
    if (!options) return 1;

    // Use cache for frequently accessed option positions
    const cacheKey = `${optionName}-${options.length}`;
    if (this.optionCache.has(cacheKey)) {
      return this.optionCache.get(cacheKey);
    }

    const option = options.find(opt => opt.name === optionName);
    const position = option ? option.position : 1;

    // Cache the result
    this.optionCache.set(cacheKey, position);
    return position;
  }

  // Find variant that matches all selected options
  findMatchingVariant(productData, selectedOptions) {
    if (!productData.variants) return null;

    // If no options are selected, return the first available variant
    if (Object.keys(selectedOptions).length === 0) {
      return productData.variants.find(variant =>
        variant.inventory === undefined || variant.inventory > 0
      ) || productData.variants[0];
    }

    // Create cache key for this combination
    const cacheKey = `${productData.id}-${JSON.stringify(selectedOptions)}`;
    if (this.variantCache.has(cacheKey)) {
      return this.variantCache.get(cacheKey);
    }

    const result = productData.variants.find(variant => {
      // Try different approaches to match variants
      const variantTitle = variant.title || '';
      const variantOptions = variantTitle.split(' / ');

      // Method 1: Match by variant title parts (most common)
      const matchesByTitle = Object.keys(selectedOptions).every(optionName => {
        const optionPosition = this.getOptionPosition(optionName, productData.options);
        const variantValue = variantOptions[optionPosition - 1]; // Convert to 0-based index
        const selectedValue = selectedOptions[optionName];
        return variantValue === selectedValue;
      });

      if (matchesByTitle) {
        return true;
      }

      // Method 2: Try to match by variant properties (option1, option2, etc.)
      const matchesByProperties = Object.keys(selectedOptions).every(optionName => {
        const optionPosition = this.getOptionPosition(optionName, productData.options);
        const variantValue = variant[`option${optionPosition}`];
        const selectedValue = selectedOptions[optionName];
        return variantValue === selectedValue;
      });

      return matchesByProperties;
    });

    // Cache the result
    this.variantCache.set(cacheKey, result);
    return result;
  }

  // Check if variant is available considering current selections
  isVariantAvailable(optionName, value, productId, currentSelections = {}) {
    const productData = window.productCardManager?.productDataStore[productId];
    if (!productData || !productData.variants) return true;

    // Check if this is a single-variant product (no real choice)
    const hasMultipleChoices = productData.options &&
      productData.options.some(option => option.values.length > 1);

    if (!hasMultipleChoices) {
      // For single-variant products, check if any variant is available
      return productData.variants.some(variant =>
        variant.inventory === undefined || variant.inventory > 0
      );
    }

    // For multi-variant products, check if any variant with this option value is available
    // considering current selections
    return productData.variants.some(variant => {
      const variantTitle = variant.title || '';
      const variantOptions = variantTitle.split(' / ');

      // Check if this variant has the selected option value
      const optionPosition = this.getOptionPosition(optionName, productData.options);
      const hasOptionValue = variantOptions[optionPosition - 1] === value;

      if (!hasOptionValue) return false;

      // Check if this variant is compatible with current selections
      const isCompatibleWithCurrentSelections = Object.keys(currentSelections).every(selectedOptionName => {
        if (selectedOptionName === optionName) return true; // Skip the option being checked

        const selectedOptionPosition = this.getOptionPosition(selectedOptionName, productData.options);
        const variantValue = variantOptions[selectedOptionPosition - 1];
        const selectedValue = currentSelections[selectedOptionName];

        return variantValue === selectedValue;
      });

      const isAvailable = variant.inventory === undefined || variant.inventory > 0;

      return isCompatibleWithCurrentSelections && isAvailable;
    });
  }

  // Update variant price from selection
  updateVariantPriceFromSelection(variant, productId) {
    const priceElement = document.querySelector(`[data-product-id="${productId}"] .product-card__price`);
    if (!priceElement) {
      console.error('❌ Price element not found for product:', productId);
      return;
    }

    // Try different price properties
    let priceAmount = variant.price || variant.price_amount || variant.price_original;

    if (!priceAmount) {
      console.error('❌ No price found for variant:', variant);
      return;
    }

    // Handle different price formats
    if (typeof priceAmount === 'object' && priceAmount.amount) {
      priceAmount = priceAmount.amount;
    }

    // Use currency from product data or variant
    const productData = window.productCardManager?.productDataStore[productId];
    let priceCurrency = productData?.price?.currency_code || variant.currency_code || "INR";

    // If price is an object with currency
    if (typeof variant.price === 'object' && variant.price.currency_code) {
      priceCurrency = variant.price.currency_code;
    }

    const formattedPrice = formatPrice(priceAmount, priceCurrency);
    priceElement.textContent = formattedPrice;
  }

  // Update availability for variant
  updateAvailability(variant, productCard) {
    const qtyInput = productCard.querySelector('.qty-input');
    if (qtyInput) {
      const inv = typeof variant.inventory === 'number' ? variant.inventory : null;
      if (inv !== null && inv >= 1) {
        qtyInput.max = String(inv);
        if (parseInt(qtyInput.value) > inv) qtyInput.value = String(inv);
      } else {
        qtyInput.removeAttribute('max');
      }
    }
  }

  // Show variant unavailable state
  showVariantUnavailable(productId) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (productCard) {
      const productData = window.productCardManager?.productDataStore[productId];

      // Check if this is a single-variant product
      const hasMultipleChoices = productData.options &&
        productData.options.some(option => option.values.length > 1);

      if (!hasMultipleChoices) {
        // For single-variant products, check if any variant is available
        const hasAvailableVariant = productData.variants.some(variant =>
          variant.inventory === undefined || variant.inventory > 0
        );

        if (hasAvailableVariant) {
          // Product is available, don't show "Select Options"
          return;
        }
      }

      const addToCartBtn = productCard.querySelector('.product-card__btn');
      if (addToCartBtn) {
        addToCartBtn.textContent = 'Select Options';
        addToCartBtn.disabled = true;
      }
    }
  }
}

// Export for use in other files
window.VariantManager = VariantManager;
