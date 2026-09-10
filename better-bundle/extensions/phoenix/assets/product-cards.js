// Function to format price with proper currency formatting using Intl.NumberFormat
function formatPrice(amount, currencyCode) {
  try {
    // Handle missing or invalid currency
    if (
      !currencyCode ||
      typeof currencyCode !== "string" ||
      currencyCode.trim() === ""
    ) {
      this.logger.warn("⚠️ Invalid currency, using USD as fallback:", currencyCode);
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
    this.logger = window.phoenixLogger || console; // Use the global logger with fallback
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
  }

  // The skeleton is already in the page.
  //
  // This used to clear .swiper-wrapper and rebuild four placeholder slides from
  // a second copy of the markup, then initialise Swiper on them. That is why a
  // shopper saw two different skeletons in sequence: the Liquid one from
  // skeleton-loader.liquid, then this one, whose markup had drifted from it
  // (no image-container, no &nbsp; fillers). Rendering it a second time from JS
  // bought nothing — the server already shipped it in the initial HTML, which
  // is both earlier and free — and kept two copies of the same markup that had
  // to be edited in lockstep.
  showSkeletonLoading() {
    this.setSkeletonState('loading');
  }

  // Update product cards with real recommendations
  updateProductCards(
    recommendations,
    analyticsApi = null,
    context = "cart",
    trackRecommendationView = null,
  ) {
    const swiperWrapper = document.querySelector(".better-bundle-recommendations .swiper-wrapper");
    if (!swiperWrapper) {
      this.logger.error('❌ ProductCardManager: Swiper wrapper not found');
      return;
    }


    // Check if we're already showing real content to prevent duplication
    if (this.skeletonState === 'loaded') {
      this.logger.warn('⚠️ ProductCardManager: Real content already loaded, skipping skeleton update');
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
        });

        // Create new slides from recommendations
        recommendations.forEach((product, index) => {
          const slide = this.createProductSlide(
            product,
            index,
            analyticsApi,
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
            this.logger.warn('🔄 Skipping Swiper reinitialization during dropdown updates');
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

      } catch (error) {
        this.logger.error('❌ ProductCardManager: Error updating product cards:', error);
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
    context = "cart",
  ) {
    if (this.renderer) {
      return this.renderer.createProductSlide(product, index, analyticsApi, context);
    } else {
      this.logger.error('❌ ProductCardRenderer not loaded');
      return null;
    }
  }

  // Handle variant selection for any option type
  selectVariant(productId, optionName, selectedValue) {

    const productData = this.productDataStore[productId];
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);

    if (!productData) {
      this.logger.error('❌ Product data not found for:', productId);
      return;
    }

    if (!productCard) {
      this.logger.error('❌ Product card not found for:', productId);
      return;
    }


    // Update visual state of the dropdown
    const dropdown = productCard.querySelector(`[data-option="${optionName}"]`);
    if (dropdown) {
      dropdown.classList.add('selected');
    } else {
      this.logger.warn('⚠️ Dropdown not found for option:', optionName);
    }

    // ✅ Get all selected options and check if complete selection
    const selectedOptions = this.dropdownManager ?
      this.dropdownManager.getSelectedOptions(productCard) :
      {};

    // Check if ALL options are selected
    const allOptionsSelected = productData.options &&
      productData.options.length > 0 &&
      Object.keys(selectedOptions).length === productData.options.length;

    if (allOptionsSelected) {
      // All options selected - find matching variant and update button
      const matchingVariant = this.variantManager ?
        this.variantManager.findMatchingVariant(productData, selectedOptions) :
        null;

      if (matchingVariant) {
        if (this.variantManager) {
          this.variantManager.updateVariantPriceFromSelection(matchingVariant, productId);
          // ✅ updateAvailability shows "Add to cart" or "Out of stock" based on inventory
          this.variantManager.updateAvailability(matchingVariant, productCard);
        }
      } else {
        // Shouldn't happen - all options match should find a variant
        this.logger.warn('⚠️ No variant match for complete selection', {
          productId,
          selectedOptions,
          options: productData.options
        });

        const addToCartBtn = productCard.querySelector('.product-card__btn');
        if (addToCartBtn) {
          addToCartBtn.disabled = true;
          addToCartBtn.textContent = 'Select Options';
          addToCartBtn.style.opacity = '0.6';
          addToCartBtn.style.cursor = 'not-allowed';
        }
      }
    } else {
      // Not all options selected yet - keep button enabled but show "Select Options" if needed
      const addToCartBtn = productCard.querySelector('.product-card__btn');
      if (addToCartBtn && Object.keys(selectedOptions).length > 0) {
        addToCartBtn.disabled = true;
        addToCartBtn.textContent = 'Select Options';
        addToCartBtn.style.opacity = '0.6';
        addToCartBtn.style.cursor = 'not-allowed';
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
      this.logger.error('❌ SwiperManager not loaded');
    }
  }

  // Initialize Swiper
  initializeSwiper() {
    if (this.swiperManager) {
      this.swiperManager.initializeSwiper();
    } else {
      this.logger.error('❌ SwiperManager not loaded');
    }
  }

  // Handle a click through to the recommended product's own page.
  //
  // This is the path the stamp cannot cover: the shopper will add the product
  // using the theme's own button on a page Phoenix does not control. Reporting
  // the click is the last observation available, and the backend reconciles it
  // against the order later by checking whether this exact product was bought.
  //
  // The report is deliberately not awaited. Navigation follows immediately and
  // the request carries `keepalive` so it survives the unload.
  handleProductClick(productId, position, productUrl, impressionId) {
    if (window.phoenixAttribution && impressionId) {
      window.phoenixAttribution.reportClick(impressionId);
    }

    if (productUrl) {
      window.location.href = productUrl;
    }
  }

  // Handle add to cart: stamp the line, then report the acceptance.
  async handleAddToCart(productId, variantId, position, context) {
    // Get the selected variant and quantity
    const productCard = document
      .querySelector(`[data-product-id="${productId}"]`)
      .closest(".product-card");

    // The impression this card was served from. Without it the add cannot be
    // attributed, so it is read from the card rather than passed around.
    const impressionId = productCard ? productCard.dataset.impressionId : "";
    const variantSelect = productCard.querySelector(".variant-selector");
    const qtyInput = productCard.querySelector(".qty-input");

    const selectedVariantId = variantSelect ? variantSelect.value : variantId;
    const selectedQuantity = qtyInput ? parseInt(qtyInput.value) : 1;

    // ✅ Check if variant is available before adding to cart
    const productData = this.productDataStore[productId];
    if (productData && productData.variants && selectedVariantId) {
      const selectedVariant = productData.variants.find(v => String(v.variant_id) === String(selectedVariantId));
      // ✅ Backend ensures variants are in-stock, but check inventory for quantity capping
      if (selectedVariant && typeof selectedVariant.inventory === 'number' && selectedVariant.inventory > 0) {
        const cappedQty = Math.max(1, Math.min(selectedQuantity, selectedVariant.inventory));
        if (cappedQty !== selectedQuantity && qtyInput) {
          qtyInput.value = String(cappedQty);
        }
      }
    }

    // Validate variant ID
    if (!selectedVariantId || selectedVariantId === '') {
      this.logger.error('No valid variant ID found:', { selectedVariantId, variantId, variantSelect });
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

      // Stamp the impression onto the cart line. Shopify promotes line item
      // properties to the order, so this survives checkout and is what the
      // backend attributes on — no session correlation involved.
      const itemProperties = window.phoenixAttribution
        ? window.phoenixAttribution.cartProperties({
            impressionId: impressionId,
            productId: productId,
            context: context,
            position: position,
            quantity: selectedQuantity,
          })
        : {};


      // Report the acceptance. Not awaited: the stamp on the cart line is the
      // authoritative record, so a failed report costs a dashboard update, not
      // the attribution itself.
      if (window.phoenixAttribution && impressionId) {
        const productData = this.productDataStore[productId] || {};
        const unitPrice = Number(productData.price_amount || productData.price || 0);
        window.phoenixAttribution.reportAccepted(
          impressionId,
          unitPrice * selectedQuantity,
        );
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


      window.location.reload();
    } catch (error) {
      this.logger.error("Error adding to cart:", error);

      // Handle specific error cases
      if (error.status === 422 || error.statusCode === 422) {
        // 422 = Unprocessable Entity (usually means out of stock or invalid variant)
        this.logger.warn('❌ Item unavailable (422):', {
          variantId: selectedVariantId,
          error: error.message || error.data
        });

        // Update variant inventory to 0 in our data store to reflect reality
        if (productData && productData.variants) {
          const variant = productData.variants.find(v => String(v.variant_id) === String(selectedVariantId));
          if (variant) {
            variant.inventory = 0; // Mark as out of stock
            this.logger.info('✅ Updated variant inventory to 0:', selectedVariantId);
          }
        }

        // Update button to show out of stock
        if (addToCartButton) {
          addToCartButton.disabled = true;
          addToCartButton.textContent = 'Out of stock';
          addToCartButton.style.opacity = '0.6';
          addToCartButton.style.cursor = 'not-allowed';

          // Update variant manager to reflect out of stock state
          if (this.variantManager && productCard) {
            const variant = productData?.variants?.find(v => String(v.variant_id) === String(selectedVariantId));
            if (variant) {
              this.variantManager.updateAvailability(variant, productCard);
            }
          }
        }

        // Show user-friendly error message (optional - can be removed if you don't want notifications)
        if (window.Shopify && window.Shopify.notify) {
          window.Shopify.notify('This item is currently out of stock', { status: 'error', duration: 3000 });
        }
      } else {
        // Generic error - restore button state
        if (addToCartButton) {
          addToCartButton.disabled = false;
          addToCartButton.style.cursor = "pointer";
          addToCartButton.textContent = originalButtonText;

          // Show generic error message
          if (window.Shopify && window.Shopify.notify) {
            window.Shopify.notify('Unable to add item to cart. Please try again.', { status: 'error', duration: 3000 });
          }
        }
      }

    }
  }
}

// Export for use in other files
window.ProductCardManager = ProductCardManager;

// Create global instance for use in HTML onclick handlers
window.productCardManager = new ProductCardManager();