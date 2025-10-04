// Function to format price with proper currency formatting using Intl.NumberFormat
function formatPrice(amount, currencyCode) {
  try {
    // Handle missing or invalid currency
    if (
      !currencyCode ||
      typeof currencyCode !== "string" ||
      currencyCode.trim() === ""
    ) {
      console.log("⚠️ Invalid currency, using USD as fallback:", currencyCode);
      currencyCode = "USD";
    }

    const numericAmount = parseFloat(amount);

    // Currency-specific locale mapping for proper symbol display
    const currencyLocaleMap = {
      INR: "en-IN", // Indian Rupee (₹)
      USD: "en-US", // US Dollar ($)
      EUR: "en-EU", // Euro (€)
      GBP: "en-GB", // British Pound (£)
      CAD: "en-CA", // Canadian Dollar (C$)
      AUD: "en-AU", // Australian Dollar (A$)
      JPY: "ja-JP", // Japanese Yen (¥)
      KRW: "ko-KR", // Korean Won (₩)
      CNY: "zh-CN", // Chinese Yuan (¥)
      BRL: "pt-BR", // Brazilian Real (R$)
      MXN: "es-MX", // Mexican Peso ($)
    };

    // Get appropriate locale for currency, fallback to en-US
    const locale = currencyLocaleMap[currencyCode] || "en-US";

    // Use Intl.NumberFormat for proper currency formatting
    const formatter = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits:
        currencyCode === "JPY" || currencyCode === "KRW" ? 0 : 2,
      maximumFractionDigits:
        currencyCode === "JPY" || currencyCode === "KRW" ? 0 : 2,
    });

    let formattedPrice = formatter.format(numericAmount);

    // Custom symbol replacement for Shopify store preferences
    if (currencyCode === "INR") {
      // Replace ₹ with Rs if store uses Rs
      formattedPrice = formattedPrice.replace("₹", "Rs. ");
    }

    return formattedPrice;
  } catch (error) {
    // Fallback formatting if Intl.NumberFormat fails
    const numericAmount = parseFloat(amount);

    // Custom symbol mapping for fallback
    const currencySymbols = {
      INR: "Rs",
      USD: "$",
      EUR: "€",
      GBP: "£",
      JPY: "¥",
      KRW: "₩",
      CAD: "C$",
      AUD: "A$",
      BRL: "R$",
      MXN: "$",
    };

    const symbol = currencySymbols[currencyCode] || currencyCode;

    if (currencyCode === "JPY" || currencyCode === "KRW") {
      return `${symbol} ${Math.round(numericAmount).toLocaleString()}`;
    } else {
      return `${symbol} ${numericAmount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
  }
}

class ProductCardManager {
  constructor() {
    this.productDataStore = {};
    // RecommendationAPI is loaded globally from api.js
    this.api =
      window.recommendationApi ||
      (window.RecommendationAPI ? new window.RecommendationAPI() : null);
  }

  // Update product cards with real recommendations
  updateProductCards(
    recommendations,
    analyticsApi = null,
    sessionId,
    context = "cart",
  ) {
    const swiperWrapper = document.querySelector(".swiper-wrapper");
    if (!swiperWrapper) {
      console.error('❌ ProductCardManager: Swiper wrapper not found');
      return;
    }

    console.log('🔄 ProductCardManager: Updating product cards with', recommendations.length, 'recommendations');

    // Hide skeleton container when real content is loaded
    const skeletonContainer = document.querySelector('.skeleton-container');
    if (skeletonContainer) {
      skeletonContainer.style.display = 'none';
      console.log('✅ ProductCardManager: Hiding skeleton - real content loaded');
    }

    // Add fade-out transition to existing skeleton slides
    const existingSlides = swiperWrapper.querySelectorAll('.swiper-slide');
    existingSlides.forEach(slide => {
      const skeletons = slide.querySelectorAll('.loading-skeleton');
      skeletons.forEach(skeleton => {
        skeleton.classList.add('fade-out');
      });
    });

    // Wait for fade-out transition, then replace content
    setTimeout(() => {
      try {
        // Clear existing slides
        swiperWrapper.innerHTML = "";

        // Store product data for variant price updates
        recommendations.forEach((product) => {
          this.productDataStore[product.id] = product;
          console.log('🏪 Stored product data:', {
            productId: product.id,
            productTitle: product.title,
            options: product.options,
            variants: product.variants?.length,
            storedData: this.productDataStore[product.id]
          });
        });

        // Create new slides from recommendations
        recommendations.forEach((product, index) => {
          const slide = this.createProductSlide(
            product,
            index,
            analyticsApi,
            sessionId,
            context,
          );

          // Add real-content class for fade-in animation
          const productCard = slide.querySelector('.product-card');
          if (productCard) {
            productCard.classList.add('real-content');
          }

          swiperWrapper.appendChild(slide);
        });

        // Reinitialize Swiper with new content after a small delay
        setTimeout(() => {
          this.initializeSwiper();
        }, 200);
        console.log('✅ ProductCardManager: Successfully updated product cards');
      } catch (error) {
        console.error('❌ ProductCardManager: Error updating product cards:', error);
        // Fallback: hide the carousel if there's an error
        const carouselContainer = document.querySelector('.shopify-app-block');
        if (carouselContainer) {
          carouselContainer.style.display = 'none';
        }
      }
    }, 300); // Match the CSS transition duration
  }

  // Create product slide from recommendation data
  createProductSlide(
    product,
    index,
    analyticsApi = null,
    sessionId,
    context = "cart",
  ) {
    const slide = document.createElement("div");
    slide.className = "swiper-slide";

    // Get default variant using selectedVariantId from API or first available variant
    let defaultVariant = null;
    if (product.selectedVariantId && product.variants) {
      defaultVariant = product.variants.find(v => v.variant_id === product.selectedVariantId);
    }
    if (!defaultVariant && product.variants && product.variants.length > 0) {
      defaultVariant = product.variants.find((v) => v.inventory > 0) || product.variants[0];
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

    // Debug logging
    console.log("💰 Price formatting:", {
      priceAmount,
      priceCurrency,
      displayPrice,
      originalPrice: price,
      productPrice: product.price,
      defaultVariantPrice: defaultVariant?.price,
    });

    // Create variants options using dynamic variant detection
    let variantOptions = "";
    const maxInventory = product.inventory || (defaultVariant?.inventory || 0);

    console.log('🎯 Creating variant options for product:', {
      productId: product.id,
      productTitle: product.title,
      hasOptions: !!(product.options && product.options.length > 0),
      optionsCount: product.options?.length || 0,
      hasVariants: !!(product.variants && product.variants.length > 1),
      variantsCount: product.variants?.length || 0
    });

    if (product.options && product.options.length > 0) {
      // Use dynamic variant detection for better UX
      variantOptions = this.createDynamicVariantSelectors(product, defaultVariant);
      console.log('✅ Created variant options from options:', variantOptions);
    } else if (product.variants && product.variants.length > 1) {
      // Fallback to variants data with dynamic detection
      variantOptions = this.createDynamicVariantSelectors(product, defaultVariant);
      console.log('✅ Created variant options from variants:', variantOptions);
    } else {
      console.log('❌ No variant options created for product:', product.id);
    }

    // TEMPORARY: Force create simple dropdowns for testing
    if (!variantOptions && product.options && product.options.length > 0) {
      console.log('🧪 Creating test variant selectors...');
      variantOptions = this.createTestVariantSelectors(product);
    }

    slide.innerHTML = `
      <div class="product-card" data-product-id="${product.id}" onclick="productCardManager.handleProductClick('${product.id}', ${index + 1}, '${product.url || ''}', '${sessionId || ''}')">
        <img
          class="product-card__image"
          src="${product.image?.url || "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjY2NjY2NjIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIyNCIgZmlsbD0iIzY2NjY2NiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg=="}"
          alt="${product.image?.alt_text || product.title}"
          loading="lazy"
        >
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

  // Initialize product card with default selections and button state
  initializeProductCard(productId, defaultVariant) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (!productCard) {
      console.log('❌ Product card not found:', productId);
      return;
    }

    // Check if already initialized to prevent multiple initializations
    if (productCard.dataset.initialized === 'true') {
      console.log('⚠️ Product card already initialized:', productId);
      return;
    }

    console.log('🔧 Initializing product card:', productId, defaultVariant);

    // Wait a bit more for DOM to be ready
    setTimeout(() => {
      const dropdowns = productCard.querySelectorAll('.variant-select');
      console.log('🔍 Found dropdowns:', dropdowns.length);

      // Select default variants - use provided default or first available
      if (defaultVariant && defaultVariant.title) {
        const variantParts = defaultVariant.title.split(' / ');
        console.log('🎯 Setting default variants:', variantParts, 'Dropdowns:', dropdowns.length);

        dropdowns.forEach((dropdown, index) => {
          if (variantParts[index]) {
            dropdown.value = variantParts[index];
            dropdown.classList.add('selected');
            console.log('✅ Set dropdown', index, 'to:', variantParts[index]);

            // Trigger the selection logic to update price
            const optionName = dropdown.dataset.option;
            this.selectVariant(productId, optionName, variantParts[index]);
          }
        });
      } else {
        // Auto-select first available option for each dropdown
        console.log('🎯 Auto-selecting first available options');
        this.autoSelectFirstAvailable(productId);
      }

      // Mark as initialized to prevent multiple initializations
      productCard.dataset.initialized = 'true';

      // Update button state
      this.updateAddToCartButton(productId);
    }, 50);
  }

  // Auto-select first available option for each dropdown
  autoSelectFirstAvailable(productId) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (!productCard) {
      console.log('❌ Product card not found for auto-select:', productId);
      return;
    }

    const dropdowns = productCard.querySelectorAll('.variant-select');
    console.log('🎯 Auto-selecting for', dropdowns.length, 'dropdowns');

    dropdowns.forEach((dropdown, index) => {
      // Select first available option (skip the empty "Select..." option)
      const firstOption = dropdown.querySelector('option:not([value=""])');
      if (firstOption) {
        dropdown.value = firstOption.value;
        dropdown.classList.add('selected');
        console.log('✅ Auto-selected dropdown', index, 'to:', firstOption.value);

        // Trigger the selection logic to update price
        const optionName = dropdown.dataset.option;
        if (optionName) {
          this.selectVariant(productId, optionName, firstOption.value);
        } else {
          console.log('⚠️ No option name found for dropdown', index);
        }
      } else {
        console.log('❌ No options found for dropdown', index);
      }
    });
  }

  // Update add to cart button state
  updateAddToCartButton(productId) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (!productCard) return;

    const button = productCard.querySelector('.product-card__btn');
    if (!button) return;

    // Since we auto-select variants, button is always enabled
    button.disabled = false;
    button.textContent = 'Add to cart';
    button.style.opacity = '1';
    button.style.cursor = 'pointer';
  }

  // Update variant price when selection changes
  updateVariantPrice(selectElement, productId) {
    const selectedVariantId = selectElement.value;
    const productData = this.productDataStore[productId];

    if (productData && productData.variants) {
      const selectedVariant = productData.variants.find(
        (v) => String(v.variant_id) === String(selectedVariantId),
      );
      if (selectedVariant) {
        const priceElement = document.querySelector(
          `[data-product-id="${productId}"] .product-card__price`,
        );
        if (priceElement) {
          const priceAmount = selectedVariant.price || selectedVariant.price_amount;
          // Use currency from product data (now includes currency in API response)
          const priceCurrency = productData.price?.currency_code || "INR";
          priceElement.textContent = formatPrice(priceAmount, priceCurrency);
        }

        // Update max inventory on qty input when variant changes
        const cardEl = selectElement.closest('.product-card');
        const qtyInput = cardEl?.querySelector('.qty-input');
        if (qtyInput) {
          const inv = typeof selectedVariant.inventory === 'number' ? selectedVariant.inventory : null;
          if (inv !== null && inv >= 1) {
            qtyInput.max = String(inv);
            if (parseInt(qtyInput.value) > inv) qtyInput.value = String(inv);
          } else {
            qtyInput.removeAttribute('max');
          }
        }
      }
    }
  }

  // Dynamic variant type detection
  detectVariantType(optionName, optionValues) {
    const name = optionName.toLowerCase();
    const values = optionValues.map(v => v.toLowerCase());

    // Color detection patterns
    const colorPatterns = [
      /color|colour|shade|hue/i,
      /^#[0-9a-f]{6}$/i, // Hex codes
      /^(red|blue|green|black|white|gray|navy|brown|pink|purple|orange|yellow)$/i
    ];

    // Size detection patterns
    const sizePatterns = [
      /size|fit|dimension/i,
      /^[SMLX]+$/i, // S, M, L, XL
      /^\d+$/i, // Numbers
      /^(small|medium|large|extra large)$/i
    ];

    // Material detection patterns
    const materialPatterns = [
      /material|fabric|finish|texture/i,
      /^(cotton|wool|leather|silk|denim|polyester|linen|cashmere)$/i
    ];

    // Check name patterns first
    if (colorPatterns.some(pattern => pattern.test(name))) return 'color';
    if (sizePatterns.some(pattern => pattern.test(name))) return 'size';
    if (materialPatterns.some(pattern => pattern.test(name))) return 'material';

    // Check value patterns
    if (values.some(value => colorPatterns.some(pattern => pattern.test(value)))) return 'color';
    if (values.some(value => sizePatterns.some(pattern => pattern.test(value)))) return 'size';
    if (values.some(value => materialPatterns.some(pattern => pattern.test(value)))) return 'material';

    // Check if values are mostly short (likely size/color)
    if (values.every(v => v.length <= 3)) return 'size';

    // Check if values are mostly long (likely material/style)
    if (values.every(v => v.length > 5)) return 'material';

    return 'dropdown';
  }

  // Create simple dropdown selectors with availability filtering
  createDynamicVariantSelectors(product, defaultVariant) {
    console.log('🔍 Creating variant selectors for product:', {
      productId: product.id,
      productTitle: product.title,
      options: product.options,
      variants: product.variants?.length
    });

    if (!product.options || product.options.length === 0) {
      console.log('❌ No options found for product:', product.id);
      return this.createFallbackVariantSelector(product, defaultVariant);
    }

    // Check if product has only one option with one value (no real choice)
    const hasMultipleChoices = product.options.some(option => option.values.length > 1);

    if (!hasMultipleChoices) {
      console.log('❌ No multiple choices for product:', product.id);
      // Product has no real variant choices, hide variant selectors
      return '';
    }

    // Create simple dropdown selectors for all options
    const selectors = product.options.map(option => {
      const selector = this.createDropdownSelector(option, product.id, defaultVariant);
      console.log('📝 Created selector for option:', option.name, 'Result:', selector ? 'SUCCESS' : 'EMPTY');
      return selector;
    }).join('');

    // Count the number of selectors to determine layout
    const selectorCount = product.options.length;
    const layoutClass = selectorCount === 2 ? 'two-dropdowns' : '';

    const result = `
            <div class="product-card__variants ${layoutClass}">
              ${selectors}
            </div>
          `;

    console.log('✅ Final variant selectors HTML:', result);
    return result;
  }


  // Create smart color swatches with better design
  createColorSwatches(option, productId, defaultVariant) {
    return `
      <div class="variant-option">
        <label class="variant-label">${option.name}:</label>
        <div class="color-swatches">
          ${option.values.map(value => {
      const isSelected = this.isVariantSelected(option.name, value, defaultVariant);
      const isAvailable = this.isVariantAvailable(option.name, value, productId);
      return `
              <button class="color-swatch ${isSelected ? 'selected' : ''} ${!isAvailable ? 'unavailable' : ''}" 
                      data-option="${option.name}"
                      data-value="${value}"
                      style="background-color: ${this.getColorValue(value)}"
                      onclick="event.stopPropagation(); productCardManager.selectVariant('${productId}', '${option.name}', '${value}')"
                      title="${value}">
              </button>
            `;
    }).join('')}
        </div>
      </div>
    `;
  }

  // Create smart size buttons with better design
  createSizeButtons(option, productId, defaultVariant) {
    return `
      <div class="variant-option">
        <label class="variant-label">${option.name}:</label>
        <div class="size-buttons">
          ${option.values.map(value => {
      const isSelected = this.isVariantSelected(option.name, value, defaultVariant);
      const isAvailable = this.isVariantAvailable(option.name, value, productId);
      return `
              <button class="size-button ${isSelected ? 'selected' : ''} ${!isAvailable ? 'unavailable' : ''}" 
                      data-option="${option.name}"
                      data-value="${value}"
                      onclick="event.stopPropagation(); productCardManager.selectVariant('${productId}', '${option.name}', '${value}')">
                ${value}
              </button>
            `;
    }).join('')}
        </div>
      </div>
    `;
  }

  // Create dropdown selector for complex options with availability filtering
  createDropdownSelector(option, productId, defaultVariant) {
    console.log('🔧 Creating dropdown for option:', {
      optionName: option.name,
      optionValues: option.values,
      productId: productId
    });

    // TEMPORARY: Show all values for debugging
    const availableValues = option.values;
    console.log('📊 Using all values (debug mode):', availableValues);

    // Original filtering (commented out for debugging)
    /*
    const availableValues = option.values.filter(value => {
      const isAvailable = this.isVariantAvailable(option.name, value, productId);
      console.log(`🔍 Checking availability for ${option.name}: ${value} = ${isAvailable}`);
      return isAvailable;
    });
    */

    // If no available variants, don't show the selector
    if (availableValues.length === 0) {
      console.log('❌ No available variants for option:', option.name);
      return '';
    }

    const result = `
      <div class="variant-option">
        <label class="variant-label">${option.name}:</label>
        <select class="variant-select" 
                data-option="${option.name}"
                onchange="event.stopPropagation(); productCardManager.selectVariant('${productId}', '${option.name}', this.value)"
                onclick="event.stopPropagation()">
          <option value="">Select ${option.name}</option>
          ${availableValues.map(value => {
      const isSelected = this.isVariantSelected(option.name, value, defaultVariant);
      return `<option value="${value}" ${isSelected ? 'selected' : ''}>${value}</option>`;
    }).join('')}
        </select>
      </div>
    `;

    console.log('✅ Created dropdown selector:', result);
    return result;
  }

  // Fallback selector for products without options
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

  // Test variant selectors (simple version for debugging)
  createTestVariantSelectors(product) {
    console.log('🧪 Creating test selectors for product:', product.id);

    const selectors = product.options.map(option => {
      return `
        <div class="variant-option">
          <label class="variant-label">${option.name}:</label>
          <select class="variant-select" 
                  data-option="${option.name}"
                  onchange="event.stopPropagation(); productCardManager.selectVariant('${product.id}', '${option.name}', this.value)"
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

  // Handle variant selection for any option type
  selectVariant(productId, optionName, selectedValue) {
    const productData = this.productDataStore[productId];
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);

    if (!productData || !productCard) return;

    // Update visual state of the dropdown
    const dropdown = productCard.querySelector(`[data-option="${optionName}"]`);
    if (dropdown) {
      dropdown.classList.add('selected');
      console.log('✅ Updated dropdown visual state for:', optionName, selectedValue);
    }

    // Update selection state
    this.updateSelectionState(productCard, optionName, selectedValue);

    // Get all selected options
    const selectedOptions = this.getSelectedOptions(productCard);

    // Find matching variant
    const matchingVariant = this.findMatchingVariant(productData, selectedOptions);

    if (matchingVariant) {
      this.updateVariantPriceFromSelection(matchingVariant, productId);
      this.updateAvailability(matchingVariant, productCard);
    } else {
      this.showVariantUnavailable(productId);
    }
  }

  // Update selection state for any option type
  updateSelectionState(productCard, optionName, selectedValue) {
    // Update color swatches
    const colorSwatches = productCard.querySelectorAll(`[data-option="${optionName}"].color-swatch`);
    colorSwatches.forEach(swatch => {
      swatch.classList.toggle('selected', swatch.dataset.value === selectedValue);
    });

    // Update size buttons
    const sizeButtons = productCard.querySelectorAll(`[data-option="${optionName}"].size-button`);
    sizeButtons.forEach(button => {
      button.classList.toggle('selected', button.dataset.value === selectedValue);
    });

    // Update material swatches
    const materialSwatches = productCard.querySelectorAll(`[data-option="${optionName}"].material-swatch`);
    materialSwatches.forEach(swatch => {
      swatch.classList.toggle('selected', swatch.dataset.value === selectedValue);
    });

    // Update dropdowns
    const selects = productCard.querySelectorAll(`[data-option="${optionName}"].variant-select`);
    selects.forEach(select => {
      select.value = selectedValue;
    });
  }

  // Get all selected options from the card
  getSelectedOptions(productCard) {
    const selectedOptions = {};

    // Check all option types
    const optionElements = productCard.querySelectorAll('[data-option][data-value]');
    optionElements.forEach(element => {
      if (element.classList.contains('selected') || element.value) {
        selectedOptions[element.dataset.option] = element.dataset.value || element.value;
      }
    });

    return selectedOptions;
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

    return productData.variants.find(variant => {
      return Object.keys(selectedOptions).every(optionName => {
        const optionPosition = this.getOptionPosition(optionName, productData.options);
        const variantValue = variant[`option${optionPosition}`];
        return variantValue === selectedOptions[optionName];
      });
    });
  }

  // Helper methods
  isVariantSelected(optionName, value, defaultVariant) {
    if (!defaultVariant) return false;
    const optionPosition = this.getOptionPosition(optionName, [{ name: optionName }]);
    return defaultVariant[`option${optionPosition}`] === value;
  }

  isVariantAvailable(optionName, value, productId) {
    const productData = this.productDataStore[productId];
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
    return productData.variants.some(variant => {
      // Check if this variant has the selected option value
      const variantTitle = variant.title || '';
      const optionValues = variantTitle.split(' / ');

      // Find the option position
      const optionIndex = productData.options.findIndex(opt => opt.name === optionName);
      if (optionIndex === -1) return false;

      // Check if the variant has this option value
      const hasOptionValue = optionValues[optionIndex] === value;
      const isAvailable = variant.inventory === undefined || variant.inventory > 0;

      return hasOptionValue && isAvailable;
    });
  }

  getOptionPosition(optionName, options) {
    if (!options) return 1;
    const option = options.find(opt => opt.name === optionName);
    return option ? option.position : 1;
  }

  getColorValue(colorName) {
    const colorMap = {
      'red': '#ef4444',
      'blue': '#3b82f6',
      'green': '#10b981',
      'black': '#1f2937',
      'white': '#f9fafb',
      'gray': '#6b7280',
      'navy': '#1e3a8a',
      'brown': '#92400e',
      'pink': '#ec4899',
      'purple': '#8b5cf6',
      'orange': '#f59e0b',
      'yellow': '#eab308',
      'teal': '#14b8a6',
      'indigo': '#6366f1',
      'cyan': '#06b6d4',
      'lime': '#84cc16',
      'amber': '#f59e0b',
      'emerald': '#10b981',
      'rose': '#f43f5e',
      'violet': '#8b5cf6',
      'sky': '#0ea5e9',
      'slate': '#64748b'
    };

    // If it's already a hex code, return as-is
    if (/^#[0-9a-f]{6}$/i.test(colorName)) {
      return colorName;
    }

    return colorMap[colorName.toLowerCase()] || '#e5e7eb';
  }


  updateVariantPriceFromSelection(variant, productId) {
    const priceElement = document.querySelector(`[data-product-id="${productId}"] .product-card__price`);
    if (priceElement && variant.price) {
      const priceAmount = variant.price || variant.price_amount;
      // Use currency from product data (now includes currency in API response)
      const productData = this.productDataStore[productId];
      const priceCurrency = productData?.price?.currency_code || "INR";
      priceElement.textContent = formatPrice(priceAmount, priceCurrency);
    }
  }

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

  showVariantUnavailable(productId) {
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);
    if (productCard) {
      const productData = this.productDataStore[productId];

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

  // Update quantity
  updateQuantity(button, change) {
    const qtyInput = button.parentElement.querySelector('.qty-input');
    const currentValue = parseInt(qtyInput.value) || 1;
    const min = parseInt(qtyInput.min) || 1;
    const max = qtyInput.max ? parseInt(qtyInput.max) : null;
    let newValue = currentValue + change;
    if (newValue < min) newValue = min;
    if (max !== null && newValue > max) newValue = max;
    qtyInput.value = String(newValue);
  }



  // Initialize Swiper
  initializeSwiper() {
    try {
      if (typeof Swiper !== "undefined") {
        // Always destroy existing Swiper instance if it exists
        if (window.swiper && typeof window.swiper.destroy === 'function') {
          console.log('🔄 Destroying existing Swiper instance');
          window.swiper.destroy(true, true);
          window.swiper = null;
        }

        // Simple loop configuration - always enable loop
        const shouldLoop = true;

        // Swiper is loaded globally from CDN
        window.swiper = new window.Swiper(".swiper", {
          breakpoints: {
            320: { slidesPerView: 1, spaceBetween: 20 },
            640: { slidesPerView: 2, spaceBetween: 20 },
            1024: { slidesPerView: 3, spaceBetween: 25 },
            1280: { slidesPerView: 4, spaceBetween: 30 },
          },
          autoplay: window.swiperConfig?.enable_autoplay
            ? {
              delay: window.swiperConfig.autoplay_delay || 2500,
              disableOnInteraction: true,
              pauseOnMouseEnter: true,
            }
            : false,
          loop: shouldLoop,
          spaceBetween: 30,
          freeMode: false,
          grabCursor: true,
          navigation: window.swiperConfig?.show_arrows
            ? {
              nextEl: ".swiper-button-next",
              prevEl: ".swiper-button-prev",
            }
            : false,
          pagination: window.swiperConfig?.show_pagination
            ? {
              el: ".swiper-pagination",
              clickable: true,
              dynamicBullets: false,
              dynamicMainBullets: 1,
            }
            : false,
          on: {
            init: function () {
              console.log("✅ Swiper initialized with recommendations!");
            },
          },
        });
      }
    } catch (error) {
      console.error('❌ Swiper initialization failed:', error);
      // Continue without Swiper - variants should still work
    }
  }

  // Handle product click with unified analytics tracking
  handleProductClick(productId, position, productUrl, sessionId) {
    if (window.analyticsApi && sessionId) {
      // Track click interaction using unified analytics
      const shopDomain = window.shopDomain;
      const customerId = window.customerId;

      window.analyticsApi
        .trackRecommendationClick(
          shopDomain,
          "cart",
          productId,
          position,
          customerId,
          { source: "cart_recommendation" }
        )
        .catch((error) => {
          console.error("Failed to track product click:", error);
        });
    }

    // Navigate to product page with attribution
    if (productUrl && window.analyticsApi && sessionId) {
      const urlWithAttribution = window.analyticsApi.addAttributionToUrl(
        productUrl,
        productId,
        position,
        sessionId,
      );
      window.location.href = urlWithAttribution;
    } else if (productUrl) {
      window.location.href = productUrl;
    }
  }

  // Handle add to cart with analytics tracking and order attributes
  async handleAddToCart(productId, variantId, position, sessionId, context) {
    // Get the selected variant and quantity
    const productCard = document
      .querySelector(`[data-product-id="${productId}"]`)
      .closest(".product-card");
    const variantSelect = productCard.querySelector(".variant-selector");
    const qtyInput = productCard.querySelector(".qty-input");

    const selectedVariantId = variantSelect ? variantSelect.value : variantId;
    const selectedQuantity = qtyInput ? parseInt(qtyInput.value) : 1;

    // Enforce inventory cap at the time of add to cart
    const productData = this.productDataStore[productId];
    if (productData && productData.variants && selectedVariantId) {
      const selectedVariant = productData.variants.find(v => String(v.variant_id) === String(selectedVariantId));
      if (selectedVariant && typeof selectedVariant.inventory === 'number' && selectedVariant.inventory >= 0) {
        const cappedQty = Math.max(1, Math.min(selectedQuantity, selectedVariant.inventory));
        if (cappedQty !== selectedQuantity && qtyInput) {
          qtyInput.value = String(cappedQty);
        }
      }
    }

    // Validate variant ID
    if (!selectedVariantId || selectedVariantId === '') {
      console.error('No valid variant ID found:', { selectedVariantId, variantId, variantSelect });
      throw new Error('No valid variant ID found');
    }

    // Show loading state
    const addToCartButton = productCard.querySelector(".product-card__btn");
    const originalButtonText = addToCartButton.textContent;

    try {
      addToCartButton.disabled = true;
      addToCartButton.style.cursor = "not-allowed";
      addToCartButton.innerHTML =
        '<span style="display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top: 2px solid transparent; border-radius: 50%; animation: spin 1s linear infinite;"></span>';

      // Build per-item attribution properties (hidden from customer display)
      const itemProperties = {
        "_bb_rec_session_id": sessionId || "",
        "_bb_rec_product_id": productId || "",
        "_bb_rec_extension": "phoenix",
        "_bb_rec_context": context || "cart",
        "_bb_rec_position": String(position || ""),
        "_bb_rec_timestamp": new Date().toISOString(),
        "_bb_rec_source": "betterbundle",
      };

      console.log('Adding to cart:', { selectedVariantId, selectedQuantity, itemProperties });


      if (window.analyticsApi && sessionId) {
        const shopDomain = window.shopDomain;
        const customerId = window.customerId;

        console.log('🔄 Tracking add to cart BEFORE cart API call to prevent cancellation');

        // Use sendBeacon for reliable delivery even during page navigation
        const trackingPromise = window.analyticsApi.trackAddToCart(
          shopDomain,
          context,
          productId,
          selectedVariantId,
          position,
          customerId,
          {
            source: "cart_recommendation",
            variant_id: selectedVariantId,
            quantity: selectedQuantity,
          }
        );

        // Don't await the tracking - let it complete in background
        trackingPromise.catch((error) => {
          console.warn('Analytics tracking failed (non-blocking):', error);
        });
      }

      // Add to cart via Shopify API with line item properties
      const response = await this.api.addToCart(
        selectedVariantId,
        selectedQuantity,
        itemProperties,
      );

      // Restore button state
      addToCartButton.disabled = false;
      addToCartButton.style.cursor = "pointer";
      addToCartButton.textContent = originalButtonText;

      // Show success feedback
      console.log("Success: Product added to cart!");

      // Trigger multiple cart update events for different themes
      if (typeof window.dispatchEvent === "function") {
        // Standard Shopify events
        window.dispatchEvent(new CustomEvent("cart:updated"));
        window.dispatchEvent(new CustomEvent("cart:refresh"));
        window.dispatchEvent(
          new CustomEvent("cart:updated", { detail: { cart: response } }),
        );

        // Theme-specific events
        window.dispatchEvent(new CustomEvent("cartUpdated"));
        window.dispatchEvent(new CustomEvent("cart:build"));
        window.dispatchEvent(new CustomEvent("cart:change"));

        // Additional events for better theme compatibility
        window.dispatchEvent(
          new CustomEvent("cart:add", { detail: { cart: response } }),
        );
        window.dispatchEvent(new CustomEvent("cart:reload"));
        window.dispatchEvent(new CustomEvent("cart:refresh-all"));
      }

      // Try different theme cart refresh methods
      if (typeof window.theme !== "undefined") {
        if (window.theme.cartDrawer) {
          window.theme.cartDrawer.refresh();
        }
        if (window.theme.cart) {
          window.theme.cart.refresh();
        }
        if (window.theme.cartUpdate) {
          window.theme.cartUpdate();
        }
      }

      // Cart is already updated via /cart/add.js and cart:updated event dispatched
      console.log("🛒 Cart updated via native API:", response);

      // Use the cart data from the add API response to update theme cart
      await this.updateThemeCartFromResponse(response);
    } catch (error) {
      console.error("Error adding to cart:", error);

      // Restore button state on error
      if (addToCartButton) {
        addToCartButton.disabled = false;
        addToCartButton.style.cursor = "pointer";
        addToCartButton.textContent = originalButtonText;
      }

      console.error("Error: Failed to add product to cart");
    }
  }

  // Simple cart update with page reload
  async updateThemeCartFromResponse(cartResponse) {
    console.log("🛒 Product added to cart successfully:", cartResponse);
    console.log("🔄 Reloading page to update cart...");
    window.location.reload();
  }

}

// Export for use in other files
window.ProductCardManager = ProductCardManager;

// Create global instance for use in HTML onclick handlers
window.productCardManager = new ProductCardManager();
