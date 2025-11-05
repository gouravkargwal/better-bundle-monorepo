/**
 * ProductCardRenderer - Handles product card rendering and DOM manipulation
 * Optimized for performance with efficient DOM operations
 */
class ProductCardRenderer {
  constructor() {
    this.cachedElements = new Map();
  }

  // Performance helper - cache DOM elements
  getCachedElement(selector, productId = null) {
    const cacheKey = productId ? `${selector}-${productId}` : selector;

    if (!this.cachedElements.has(cacheKey)) {
      const element = productId
        ? document.querySelector(`[data-product-id="${productId}"] ${selector}`)
        : document.querySelector(selector);
      this.cachedElements.set(cacheKey, element);
    }

    return this.cachedElements.get(cacheKey);
  }

  // Clear cache for a specific product
  clearProductCache(productId) {
    for (const [key, value] of this.cachedElements.entries()) {
      if (key.includes(productId)) {
        this.cachedElements.delete(key);
      }
    }
  }

  // Create product slide from recommendation data
  createProductSlide(product, index, analyticsApi = null, sessionId, context = "cart") {
    const slide = document.createElement("div");
    slide.className = "swiper-slide";

    // ✅ Backend guarantees selectedVariantId is always in-stock, so trust it directly
    let defaultVariant = null;
    if (product.selectedVariantId && product.variants) {
      defaultVariant = product.variants.find(v => String(v.variant_id) === String(product.selectedVariantId));
    }

    // Fallback to first variant only if selectedVariantId not found (shouldn't happen with backend fix)
    if (!defaultVariant && product.variants && product.variants.length > 0) {
      defaultVariant = product.variants[0];
    }

    // Handle price data - could be from variant or product level
    let price = product.price;

    if (defaultVariant) {
      price = defaultVariant.price || product.price;
    }

    // Format price for display
    const priceAmount = typeof price === "object" ? price.amount : price;
    const priceCurrency =
      typeof price === "object"
        ? price.currency_code
        : product.price?.currency_code || "USD";
    const displayPrice = formatPrice(priceAmount, priceCurrency);

    // Create variants options using dynamic variant detection
    let variantOptions = "";
    const maxInventory = product.inventory || (defaultVariant?.inventory || 0);

    if (product.options && product.options.length > 0) {
      // Use dynamic variant detection for better UX
      variantOptions = this.createDynamicVariantSelectors(product, defaultVariant);
    } else if (product.variants && product.variants.length > 1) {
      // Fallback to variants data with dynamic detection
      variantOptions = this.createDynamicVariantSelectors(product, defaultVariant);
    }

    // TEMPORARY: Force create simple dropdowns for testing
    if (!variantOptions && product.options && product.options.length > 0) {
      variantOptions = this.createTestVariantSelectors(product);
    }

    // Prepare images array - support both single image and multiple images
    const images = product.images && product.images.length > 0
      ? product.images
      : (product.image ? [product.image] : []);

    const mainImage = images[0] || { url: "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjY2NjY2NjIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIyNCIgZmlsbD0iIzY2NjY2NiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg==", alt_text: "No Image" };

    slide.innerHTML = `
      <div class="product-card" data-product-id="${product.id}" data-images='${JSON.stringify(images)}'>
        <div class="product-card__image-container">
          <img
            class="product-card__image"
            src="${mainImage.url}"
            alt="${mainImage.alt_text || product.title}"
            loading="lazy"
            data-product-id="${product.id}"
            data-product-index="${index + 1}"
            data-product-url="${product.url || ''}"
            data-session-id="${sessionId || ''}"
          >
          ${images.length > 1 ? `
            <div class="mobile-hint">Tap to see more</div>
          ` : ''}
        </div>
        <div class="product-card__body">
          <h4 class="product-card__title">${product.title}</h4>
          
          <!-- Line 1: Price and Quantity on same line -->
          <div class="product-card__price-quantity">
            <p class="product-card__price" data-product-id="${product.id}">${displayPrice}</p>
            <div class="product-card__quantity">
              <button class="qty-btn qty-minus" type="button" onclick="event.stopPropagation(); productCardManager.updateQuantity(this, -1)">-</button>
              <input type="number" value="1" min="1" ${maxInventory ? `max="${Math.max(1, maxInventory)}"` : ""} class="qty-input" onclick="event.stopPropagation()">
              <button class="qty-btn qty-plus" type="button" onclick="event.stopPropagation(); productCardManager.updateQuantity(this, 1)">+</button>
            </div>
          </div>
          
          <!-- Line 2: Variant Dropdowns (2 side by side) -->
          <div class="product-card__variants">
            ${variantOptions}
          </div>
          
          <!-- Line 3: Add to Cart Button -->
          <!-- ✅ Backend ensures defaultVariant is in-stock, so button is always enabled initially -->
          <button class="product-card__btn" type="button" 
            data-product-id="${product.id}"
            onclick="event.stopPropagation(); productCardManager.handleAddToCart('${product.id}', '${defaultVariant?.variant_id || ""}', ${index + 1}, '${sessionId || ""}', '${context}')">
            Add to cart
          </button>
        </div>
      </div>
    `;

    // Initialize button state and default selections with a small delay
    setTimeout(() => {
      this.initializeProductCard(product.id, defaultVariant);
    }, 100);

    return slide;
  }

  // Create dynamic variant selectors
  createDynamicVariantSelectors(product, defaultVariant) {
    if (!product.options || product.options.length === 0) {
      return this.createFallbackVariantSelector(product, defaultVariant);
    }

    // Check if product has only one option with one value (no real choice)
    const hasMultipleChoices = product.options.some(option => option.values.length > 1);

    if (!hasMultipleChoices) {
      // Product has no real variant choices, hide variant selectors
      return '';
    }

    // Create simple dropdown selectors for all options
    const selectors = product.options.map(option => {
      return this.createDropdownSelector(option, product.id, defaultVariant);
    }).join('');

    // Count the number of selectors to determine layout
    const selectorCount = product.options.length;
    const layoutClass = selectorCount === 2 ? 'two-dropdowns' : '';

    return `
      <div class="product-card__variants ${layoutClass}">
        ${selectors}
      </div>
    `;
  }

  // Create dropdown selector
  createDropdownSelector(option, productId, defaultVariant) {
    // Show all values for debugging
    const availableValues = option.values;

    // If no available variants, don't show the selector
    if (availableValues.length === 0) {
      return '';
    }

    return `
      <div class="variant-option">
        <label class="variant-label">${option.name}:</label>
        <select class="variant-select" 
                data-option="${option.name}"
                onchange="event.stopPropagation(); window.dropdownManager.handleDropdownChange('${productId}', '${option.name}', this)"
                onclick="event.stopPropagation()">
          <option value="">Select ${option.name}</option>
          ${availableValues.map(value => {
      const isSelected = this.isVariantSelected(option.name, value, defaultVariant);
      return `<option value="${value}" ${isSelected ? 'selected' : ''}>${value}</option>`;
    }).join('')}
        </select>
      </div>
    `;
  }

  // Create test variant selectors
  createTestVariantSelectors(product) {
    const selectors = product.options.map(option => {
      return `
        <div class="variant-option">
          <label class="variant-label">${option.name}:</label>
          <select class="variant-select" 
                  data-option="${option.name}"
                  onchange="event.stopPropagation(); window.dropdownManager.handleDropdownChange('${product.id}', '${option.name}', this)"
                  onclick="event.stopPropagation()">
            <option value="">Select ${option.name}</option>
            ${option.values.map(value =>
        `<option value="${value}">${value}</option>`
      ).join('')}
          </select>
        </div>
      `;
    }).join('');

    // Count the number of selectors to determine layout
    const selectorCount = product.options.length;
    const layoutClass = selectorCount === 2 ? 'two-dropdowns' : '';

    return `
      <div class="product-card__variants ${layoutClass}">
        ${selectors}
      </div>
    `;
  }

  // Create fallback variant selector
  createFallbackVariantSelector(product, defaultVariant) {
    return `
      <div class="product-card__variants">
        <select class="variant-selector" onchange="event.stopPropagation(); productCardManager.updateVariantPrice(this, '${product.id}')" onclick="event.stopPropagation()">
          ${product.variants.map((variant, i) => {
      const isSelected = variant.variant_id === defaultVariant?.variant_id;
      const variantTitle = variant.title || `Option ${i + 1}`;
      const isAvailable = variant.inventory === undefined || variant.inventory > 0;
      return `<option value="${variant.variant_id}" ${isSelected ? "selected" : ""} ${!isAvailable ? "disabled" : ""}>
                      ${variantTitle}
                    </option>`;
    }).join("")}
        </select>
      </div>
    `;
  }

  // Check if variant is selected
  isVariantSelected(optionName, value, defaultVariant) {
    if (!defaultVariant) return false;

    // Try to match by variant title first
    const variantTitle = defaultVariant.title || '';
    const variantOptions = variantTitle.split(' / ');
    const optionPosition = this.getOptionPosition(optionName, [{ name: optionName }]);
    const variantValue = variantOptions[optionPosition - 1]; // Convert to 0-based index

    if (variantValue === value) {
      return true;
    }

    // Fallback to property matching
    return defaultVariant[`option${optionPosition}`] === value;
  }

  // Get option position
  getOptionPosition(optionName, options) {
    if (!options) return 1;
    const option = options.find(opt => opt.name === optionName);
    return option ? option.position : 1;
  }

  // Initialize product card with default selections
  initializeProductCard(productId, defaultVariant) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (!productCard) {
      return;
    }

    // Check if already initialized to prevent multiple initializations
    if (productCard.dataset.initialized === 'true') {
      return;
    }

    // Wait a bit more for DOM to be ready
    setTimeout(() => {
      const dropdowns = productCard.querySelectorAll('.variant-select');

      // Select default variants - use provided default or first available
      if (defaultVariant && defaultVariant.title) {
        const variantParts = defaultVariant.title.split(' / ');

        // Set all dropdown values first WITHOUT triggering selectVariant
        dropdowns.forEach((dropdown, index) => {
          if (variantParts[index]) {
            dropdown.value = variantParts[index];
            dropdown.classList.add('selected');
          }
        });

        // Now trigger selectVariant once after ALL dropdowns are set
        // This ensures we have complete selection context for variant matching
        setTimeout(() => {
          // Get all selected options from the dropdowns
          const selectedOptions = {};
          dropdowns.forEach(dropdown => {
            const optionName = dropdown.dataset.option;
            const value = dropdown.value;
            if (optionName && value) {
              selectedOptions[optionName] = value;
            }
          });

          // Only trigger if we have at least one selection
          if (Object.keys(selectedOptions).length > 0 && window.productCardManager) {
            // Use the first option to trigger the update (which will handle all selections)
            const firstOptionName = Object.keys(selectedOptions)[0];
            const firstValue = selectedOptions[firstOptionName];
            window.productCardManager.selectVariant(productId, firstOptionName, firstValue);
          }
        }, 50); // Increased delay to ensure DOM is ready
      } else {
        // Auto-select first available option for each dropdown
        this.autoSelectFirstAvailable(productId);
      }

      // Mark as initialized to prevent multiple initializations
      productCard.dataset.initialized = 'true';

      // Update button state after a delay to ensure variant selection has processed
      setTimeout(() => {
        this.updateAddToCartButton(productId);
      }, 150);
    }, 50);
  }

  // Auto-select first available option for each dropdown
  autoSelectFirstAvailable(productId) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (!productCard) {
      return;
    }

    const dropdowns = productCard.querySelectorAll('.variant-select');

    dropdowns.forEach((dropdown, index) => {
      // Select first available option (skip the empty "Select..." option)
      const firstOption = dropdown.querySelector('option:not([value=""])');
      if (firstOption) {
        dropdown.value = firstOption.value;
        dropdown.classList.add('selected');
      }
    });
  }

  // Update add to cart button state based on current selected variant
  updateAddToCartButton(productId) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (!productCard) return;

    const button = productCard.querySelector('.product-card__btn');
    if (!button) return;

    // Get current selected variant
    const productData = window.productCardManager?.productDataStore[productId];
    if (!productData || !productData.variants) {
      button.disabled = false;
      button.textContent = 'Add to cart';
      button.style.opacity = '1';
      button.style.cursor = 'pointer';
      return;
    }

    // Get selected options from dropdowns
    const dropdownManager = window.productCardManager?.dropdownManager;
    const selectedOptions = dropdownManager ? dropdownManager.getSelectedOptions(productCard) : {};

    // Find matching variant
    const variantManager = window.productCardManager?.variantManager;
    const currentVariant = variantManager ? variantManager.findMatchingVariant(productData, selectedOptions) : null;

    // Update button based on variant availability
    if (currentVariant && variantManager) {
      variantManager.updateAvailability(currentVariant, productCard);
    } else {
      // Fallback: enable button if no variant found
      button.disabled = false;
      button.textContent = 'Add to cart';
      button.style.opacity = '1';
      button.style.cursor = 'pointer';
    }
  }
}

// Export for use in other files
window.ProductCardRenderer = ProductCardRenderer;
