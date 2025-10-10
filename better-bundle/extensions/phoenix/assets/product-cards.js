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
    this.skeletonState = 'initial'; // 'initial', 'loading', 'loaded'

    // Initialize managers with fallbacks
    this.variantManager = window.VariantManager ? new window.VariantManager() : null;
    this.dropdownManager = window.DropdownManager ? new window.DropdownManager() : null;
    this.swiperManager = window.SwiperManager ? new window.SwiperManager() : null;
    this.renderer = window.ProductCardRenderer ? new window.ProductCardRenderer() : null;

    // Set up global references for managers
    if (this.dropdownManager) window.dropdownManager = this.dropdownManager;
    if (this.swiperManager) window.swiperManager = this.swiperManager;
  }

  // Manage skeleton loading state
  setSkeletonState(state) {
    this.skeletonState = state;
    console.log(`🔄 ProductCardManager: Skeleton state changed to ${state}`);
  }

  // Show skeleton loading during API calls
  showSkeletonLoading() {
    const swiperWrapper = document.querySelector(".swiper-wrapper");
    if (!swiperWrapper) {
      console.error('❌ ProductCardManager: Swiper wrapper not found');
      return;
    }

    console.log('🔄 ProductCardManager: Updating skeleton loading...');
    this.setSkeletonState('loading');

    // Check if skeleton already exists and is visible
    const existingSkeleton = swiperWrapper.querySelector('.loading-placeholder:not(.fade-out)');
    if (existingSkeleton) {
      console.log('✅ ProductCardManager: Skeleton already exists and visible, just updating state');
      return;
    }

    // Only create skeleton if none exists or if existing ones are faded out
    console.log('🔄 ProductCardManager: Creating skeleton loading...');

    // Clear existing content
    swiperWrapper.innerHTML = '';

    // Create skeleton slides matching actual product card structure
    console.log('🔄 Creating 4 skeleton slides...');
    for (let i = 0; i < 4; i++) {
      const slide = document.createElement('div');
      slide.className = 'swiper-slide loading-placeholder';
      slide.innerHTML = `
        <div class="product-card">
          <div class="product-card__image loading-skeleton"></div>
          <div class="product-card__body">
            <h4 class="product-card__title loading-skeleton"></h4>
            
            <!-- Line 1: Price and Quantity on same line -->
            <div class="product-card__price-quantity">
              <p class="product-card__price loading-skeleton"></p>
              <div class="product-card__quantity">
                <button class="qty-btn loading-skeleton"></button>
                <input type="number" class="qty-input loading-skeleton">
                <button class="qty-btn loading-skeleton"></button>
              </div>
            </div>
            
            <!-- Line 2: Variant Dropdowns -->
            <div class="product-card__variants two-dropdowns">
              <div class="variant-option">
                <label class="variant-label loading-skeleton"></label>
                <select class="variant-select loading-skeleton"></select>
              </div>
              <div class="variant-option">
                <label class="variant-label loading-skeleton"></label>
                <select class="variant-select loading-skeleton"></select>
              </div>
            </div>
            
            <!-- Line 3: Add to Cart Button -->
            <button class="product-card__btn loading-skeleton"></button>
          </div>
        </div>
      `;
      swiperWrapper.appendChild(slide);
      console.log(`✅ Created skeleton slide ${i + 1}`);
    }

    console.log('📊 Total skeleton slides created:', swiperWrapper.children.length);

    // Initialize Swiper for skeleton
    this.initializeSwiper();
  }

  // Update product cards with real recommendations
  updateProductCards(
    recommendations,
    analyticsApi = null,
    sessionId,
    context = "cart",
    trackRecommendationView = null,
  ) {
    const swiperWrapper = document.querySelector(".swiper-wrapper");
    if (!swiperWrapper) {
      console.error('❌ ProductCardManager: Swiper wrapper not found');
      return;
    }

    console.log('🔄 ProductCardManager: Updating product cards with', recommendations.length, 'recommendations');

    // Check if we're already showing real content to prevent duplication
    if (this.skeletonState === 'loaded') {
      console.log('⚠️ ProductCardManager: Real content already loaded, skipping skeleton update');
      return;
    }

    // Set skeleton state to loading
    this.setSkeletonState('loading');

    // Add fade-out transition to existing skeleton slides
    const existingSlides = swiperWrapper.querySelectorAll('.swiper-slide');
    existingSlides.forEach(slide => {
      // Add fade-out to the entire slide if it's a skeleton
      if (slide.classList.contains('loading-placeholder')) {
        slide.classList.add('fade-out');
      }
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
            // Ensure initial state for animation
            productCard.style.opacity = '0';
            productCard.style.transform = 'scale(0.95)';
          }

          swiperWrapper.appendChild(slide);
        });

        // Only reinitialize Swiper if it doesn't exist or if content structure changed significantly
        // Skip reinitialization if we're updating dropdowns to prevent card movement
        setTimeout(() => {
          if (this.dropdownManager && this.dropdownManager.isUpdatingDropdowns) {
            console.log('🔄 Skipping Swiper reinitialization during dropdown updates');
            return;
          }

          if (this.swiperManager) {
            this.swiperManager.updateSwiper();
            this.swiperManager.preventNavigationClickPropagation();
          } else {
            this.initializeSwiper();
            this.preventNavigationClickPropagation();
          }
        }, 100);

        // Set skeleton state to loaded
        this.setSkeletonState('loaded');

        // Set up intersection observer to track when recommendations are actually viewed
        if (trackRecommendationView && recommendations.length > 0) {
          const productIds = recommendations.map(product => product.id);
          const carouselContainer = document.querySelector('.shopify-app-block');

          if (carouselContainer) {
            const observer = new IntersectionObserver(
              (entries) => {
                entries.forEach((entry) => {
                  if (entry.isIntersecting) {
                    trackRecommendationView(productIds);
                    observer.disconnect(); // Only track once
                  }
                });
              },
              { threshold: 0.1 } // Trigger when 10% of the element is visible
            );

            observer.observe(carouselContainer);
          }
        }

        console.log('✅ ProductCardManager: Successfully updated product cards');
      } catch (error) {
        console.error('❌ ProductCardManager: Error updating product cards:', error);
        // Fallback: hide the carousel if there's an error
        const carouselContainer = document.querySelector('.shopify-app-block');
        if (carouselContainer) {
          carouselContainer.style.display = 'none';
        }
      }
    }, 200); // Match the CSS transition duration
  }

  // Create product slide from recommendation data
  createProductSlide(
    product,
    index,
    analyticsApi = null,
    sessionId,
    context = "cart",
  ) {
    if (this.renderer) {
      return this.renderer.createProductSlide(product, index, analyticsApi, sessionId, context);
    } else {
      console.error('❌ ProductCardRenderer not loaded');
      return null;
    }
  }

  // Handle variant selection for any option type
  selectVariant(productId, optionName, selectedValue) {
    console.log('🎯 selectVariant called:', { productId, optionName, selectedValue });

    const productData = this.productDataStore[productId];
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);

    if (!productData) {
      console.error('❌ Product data not found for:', productId);
      return;
    }

    if (!productCard) {
      console.error('❌ Product card not found for:', productId);
      return;
    }

    console.log('✅ Found product data and card for:', productId);

    // Update visual state of the dropdown
    const dropdown = productCard.querySelector(`[data-option="${optionName}"]`);
    if (dropdown) {
      dropdown.classList.add('selected');
      console.log('✅ Updated dropdown visual state for:', optionName, selectedValue);
    } else {
      console.warn('⚠️ Dropdown not found for option:', optionName);
    }

    // Update dependent dropdowns based on current selection
    if (this.dropdownManager) {
      this.dropdownManager.updateDependentDropdowns(productId, optionName, selectedValue);
    }

    // Get all selected options
    const selectedOptions = this.dropdownManager ?
      this.dropdownManager.getSelectedOptions(productCard) :
      {};
    console.log('📋 All selected options:', selectedOptions);

    // Find matching variant
    const matchingVariant = this.variantManager ?
      this.variantManager.findMatchingVariant(productData, selectedOptions) :
      null;

    if (matchingVariant) {
      console.log('✅ Found matching variant:', matchingVariant);
      if (this.variantManager) {
        this.variantManager.updateVariantPriceFromSelection(matchingVariant, productId);
        this.variantManager.updateAvailability(matchingVariant, productCard);
      }
    } else {
      console.warn('⚠️ No matching variant found, showing unavailable');
      if (this.variantManager) {
        this.variantManager.showVariantUnavailable(productId);
      }
    }

    // Reset the dropdown update flag after a short delay to allow dependent dropdowns to complete
    setTimeout(() => {
      this.isUpdatingDropdowns = false;
    }, 200);
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

  // Prevent navigation arrows from triggering product card clicks
  preventNavigationClickPropagation() {
    if (this.swiperManager) {
      this.swiperManager.preventNavigationClickPropagation();
    } else {
      console.error('❌ SwiperManager not loaded');
    }
  }

  // Initialize Swiper
  initializeSwiper() {
    if (this.swiperManager) {
      this.swiperManager.initializeSwiper();
    } else {
      console.error('❌ SwiperManager not loaded');
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
        "_bb_rec_quantity": String(selectedQuantity || 1), // ✅ Add quantity to attributes
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
      await this.api.addToCart(
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

      // Reload page to update cart UI
      console.log("🔄 Reloading page to update cart UI...");
      window.location.reload();
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
}

// Export for use in other files
window.ProductCardManager = ProductCardManager;

// Create global instance for use in HTML onclick handlers
window.productCardManager = new ProductCardManager();