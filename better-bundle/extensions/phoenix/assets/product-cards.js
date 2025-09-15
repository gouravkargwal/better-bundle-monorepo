// Function to format price with proper currency formatting using Intl.NumberFormat
function formatPrice(amount, currencyCode) {
  try {
    const numericAmount = parseFloat(amount);

    // Currency-specific locale mapping for proper symbol display
    const currencyLocaleMap = {
      'INR': 'en-IN',  // Indian Rupee (₹)
      'USD': 'en-US',  // US Dollar ($)
      'EUR': 'en-EU',  // Euro (€)
      'GBP': 'en-GB',  // British Pound (£)
      'CAD': 'en-CA',  // Canadian Dollar (C$)
      'AUD': 'en-AU',  // Australian Dollar (A$)
      'JPY': 'ja-JP',  // Japanese Yen (¥)
      'KRW': 'ko-KR',  // Korean Won (₩)
      'CNY': 'zh-CN',  // Chinese Yuan (¥)
      'BRL': 'pt-BR',  // Brazilian Real (R$)
      'MXN': 'es-MX',  // Mexican Peso ($)
    };

    // Get appropriate locale for currency, fallback to en-US
    const locale = currencyLocaleMap[currencyCode] || 'en-US';

    // Use Intl.NumberFormat for proper currency formatting
    const formatter = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: (currencyCode === 'JPY' || currencyCode === 'KRW') ? 0 : 2,
      maximumFractionDigits: (currencyCode === 'JPY' || currencyCode === 'KRW') ? 0 : 2,
    });

    let formattedPrice = formatter.format(numericAmount);

    // Custom symbol replacement for Shopify store preferences
    if (currencyCode === 'INR') {
      // Replace ₹ with Rs if store uses Rs
      formattedPrice = formattedPrice.replace('₹', 'Rs. ');
    }

    return formattedPrice;
  } catch (error) {
    // Fallback formatting if Intl.NumberFormat fails
    const numericAmount = parseFloat(amount);

    // Custom symbol mapping for fallback
    const currencySymbols = {
      'INR': 'Rs',
      'USD': '$',
      'EUR': '€',
      'GBP': '£',
      'JPY': '¥',
      'KRW': '₩',
      'CAD': 'C$',
      'AUD': 'A$',
      'BRL': 'R$',
      'MXN': '$'
    };

    const symbol = currencySymbols[currencyCode] || currencyCode;

    if (currencyCode === 'JPY' || currencyCode === 'KRW') {
      return `${symbol} ${Math.round(numericAmount).toLocaleString()}`;
    } else {
      return `${symbol} ${numericAmount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
  }
}

class ProductCardManager {
  constructor() {
    this.productDataStore = {};
    this.api = new RecommendationAPI();
  }

  // Update product cards with real recommendations
  updateProductCards(recommendations, analyticsApi = null, sessionId = null, context = 'cart') {
    const swiperWrapper = document.querySelector('.swiper-wrapper');
    if (!swiperWrapper) return;

    // Clear existing slides
    swiperWrapper.innerHTML = '';

    // Store product data for variant price updates
    recommendations.forEach(product => {
      this.productDataStore[product.id] = product;
    });

    // Create new slides from recommendations
    recommendations.forEach((product, index) => {
      const slide = this.createProductSlide(product, index, analyticsApi, sessionId, context);
      swiperWrapper.appendChild(slide);
    });

    // Reinitialize Swiper with new content
    this.initializeSwiper();
  }

  // Create product slide from recommendation data
  createProductSlide(product, index, analyticsApi = null, sessionId = null, context = 'cart') {
    const slide = document.createElement('div');
    slide.className = 'swiper-slide';

    // Get default variant (first available variant or first variant)
    const defaultVariant = product.variants && product.variants.length > 0
      ? product.variants.find(v => v.available) || product.variants[0]
      : null;

    // Handle price data - could be from variant or product level
    let price = product.price;

    if (defaultVariant) {
      price = defaultVariant.price || product.price;
    }

    // Format price for display
    const priceAmount = typeof price === 'object' ? price.amount : price;
    const priceCurrency = typeof price === 'object' ? price.currency_code : (product.price?.currency_code || 'USD');
    const displayPrice = formatPrice(priceAmount, priceCurrency);

    // Debug logging
    console.log('💰 Price formatting:', {
      priceAmount,
      priceCurrency,
      displayPrice,
      originalPrice: price,
      productPrice: product.price,
      defaultVariantPrice: defaultVariant?.price
    });

    // Create variants options if multiple variants exist
    let variantOptions = '';
    if (product.variants && product.variants.length > 1) {
      variantOptions = `
        <div class="product-card__variants">
          <select class="variant-selector" onchange="event.stopPropagation(); productCardManager.updateVariantPrice(this, '${product.id}')" onclick="event.stopPropagation()">
            ${product.variants.map((variant, i) => {
        const isSelected = variant.id === defaultVariant?.id;
        const variantTitle = variant.title || variant.option1 || `Option ${i + 1}`;
        return `<option value="${variant.id}" ${isSelected ? 'selected' : ''}>
                ${variantTitle}
              </option>`;
      }).join('')}
          </select>
        </div>
      `;
    }

    slide.innerHTML = `
      <div class="product-card" onclick="productCardManager.handleProductClick('${product.id}', ${index + 1}, '${product.url || ''}', '${sessionId || ''}')">
        <img
          class="product-card__image"
          src="${product.image?.url || 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAwIiBoZWlnaHQ9IjQwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjY2NjY2NjIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIyNCIgZmlsbD0iIzY2NjY2NiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIEltYWdlPC90ZXh0Pjwvc3ZnPg=='}"
          alt="${product.image?.alt_text || product.title}"
          loading="lazy"
        >
        <div class="product-card__body">
          <h4 class="product-card__title">${product.title}</h4>
          <p class="product-card__price" data-product-id="${product.id}">${displayPrice}</p>
          <div class="product-card__options">
            ${variantOptions}
            <div class="product-card__quantity">
              <button class="qty-btn qty-minus" type="button" onclick="event.stopPropagation(); productCardManager.updateQuantity(this, -1)">-</button>
              <input type="number" value="1" min="1" class="qty-input" onclick="event.stopPropagation()">
              <button class="qty-btn qty-plus" type="button" onclick="event.stopPropagation(); productCardManager.updateQuantity(this, 1)">+</button>
            </div>
          </div>
          <button class="product-card__btn" type="button" 
            onclick="event.stopPropagation(); productCardManager.handleAddToCart('${product.id}', '${defaultVariant?.id || ''}', ${index + 1}, '${sessionId || ''}', '${context}')">
            Add to cart
          </button>
        </div>
      </div>
    `;

    return slide;
  }

  // Update variant price when selection changes
  updateVariantPrice(selectElement, productId) {
    const selectedVariantId = selectElement.value;
    const productData = this.productDataStore[productId];

    if (productData && productData.variants) {
      const selectedVariant = productData.variants.find(v => v.id === selectedVariantId);
      if (selectedVariant) {
        const priceElement = document.querySelector(`[data-product-id="${productId}"]`);
        if (priceElement) {
          const priceAmount = selectedVariant.price || selectedVariant.price_amount;
          const priceCurrency = selectedVariant.currency_code || 'USD';
          priceElement.textContent = formatPrice(priceAmount, priceCurrency);
        }
      }
    }
  }

  // Update quantity
  updateQuantity(button, change) {
    const qtyInput = button.parentElement.querySelector('.qty-input');
    const currentValue = parseInt(qtyInput.value);
    const newValue = Math.max(1, currentValue + change);
    qtyInput.value = newValue;
  }

  // Add to cart function
  async addToCart(productId, defaultVariantId) {
    try {
      // Get the selected variant from the dropdown
      const productCard = document.querySelector(`[data-product-id="${productId}"]`).closest('.product-card');
      const variantSelect = productCard.querySelector('.variant-selector');
      const qtyInput = productCard.querySelector('.qty-input');

      const selectedVariantId = variantSelect ? variantSelect.value : defaultVariantId;
      const selectedQuantity = qtyInput ? parseInt(qtyInput.value) : 1;

      await this.api.addToCart(selectedVariantId, selectedQuantity);

      // Show success feedback
      this.showSuccessMessage('Product added to cart!');
    } catch (error) {
      console.error('Error adding to cart:', error);
      this.showErrorMessage('Failed to add product to cart');
    }
  }

  // Show success message
  showSuccessMessage(message) {
    // You can implement a toast notification here
    console.log('Success:', message);
  }

  // Show error message
  showErrorMessage(message) {
    // You can implement a toast notification here
    console.error('Error:', message);
  }

  // Initialize Swiper
  initializeSwiper() {
    if (typeof Swiper !== 'undefined') {
      // Check number of slides to determine if loop should be enabled
      const slides = document.querySelectorAll('.swiper-slide');
      const shouldLoop = slides.length > 3; // Only loop if more than 3 slides

      new Swiper('.swiper', {
        breakpoints: {
          320: { slidesPerView: 1, spaceBetween: 20 },
          750: { slidesPerView: 2, spaceBetween: 25 },
          990: { slidesPerView: 3, spaceBetween: 30 },
          1200: { slidesPerView: 4, spaceBetween: 30 },
        },
        autoplay: window.swiperConfig?.enable_autoplay ? {
          delay: window.swiperConfig.autoplay_delay || 2500,
          disableOnInteraction: true,
          pauseOnMouseEnter: true,
        } : false,
        loop: shouldLoop, // Enable loop only if enough slides
        spaceBetween: 30,
        freeMode: false,
        grabCursor: true,
        navigation: window.swiperConfig?.show_arrows ? {
          nextEl: '.swiper-button-next',
          prevEl: '.swiper-button-prev'
        } : false,
        pagination: window.swiperConfig?.show_pagination ? {
          el: '.swiper-pagination',
          clickable: true
        } : false,
        on: {
          init: function () {
            console.log('Swiper initialized with recommendations!');
          },
        },
      });
    }
  }

  // Handle product click with analytics tracking
  handleProductClick(productId, position, productUrl, sessionId) {
    if (window.analyticsApi && sessionId) {
      // Track click interaction
      window.analyticsApi.trackInteraction({
        session_id: sessionId,
        product_id: productId,
        interaction_type: "click",
        position: position,
        extension_type: "phoenix",
        context: "cart",
        metadata: { source: "cart_recommendation" }
      }).catch(error => {
        console.error('Failed to track product click:', error);
      });
    }

    // Navigate to product page with attribution
    if (productUrl && window.analyticsApi && sessionId) {
      const urlWithAttribution = window.analyticsApi.addAttributionToUrl(productUrl, productId, position, sessionId);
      window.location.href = urlWithAttribution;
    } else if (productUrl) {
      window.location.href = productUrl;
    }
  }

  // Handle add to cart with analytics tracking and order attributes
  async handleAddToCart(productId, variantId, position, sessionId, context) {
    // Get the selected variant and quantity
    const productCard = document.querySelector(`[data-product-id="${productId}"]`).closest('.product-card');
    const variantSelect = productCard.querySelector('.variant-selector');
    const qtyInput = productCard.querySelector('.qty-input');

    const selectedVariantId = variantSelect ? variantSelect.value : variantId;
    const selectedQuantity = qtyInput ? parseInt(qtyInput.value) : 1;

    // Show loading state
    const addToCartButton = productCard.querySelector('.product-card__btn');
    const originalButtonText = addToCartButton.textContent;

    try {
      addToCartButton.disabled = true;
      addToCartButton.style.cursor = 'not-allowed';
      addToCartButton.innerHTML = '<span style="display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top: 2px solid transparent; border-radius: 50%; animation: spin 1s linear infinite;"></span> Adding...';

      // Add to cart via Shopify API
      const response = await this.api.addToCart(selectedVariantId, selectedQuantity);

      // Track add to cart interaction
      if (window.analyticsApi && sessionId) {
        await window.analyticsApi.trackInteraction({
          session_id: sessionId,
          product_id: productId,
          interaction_type: "add_to_cart",
          position: position,
          extension_type: "phoenix",
          context: context,
          metadata: {
            source: "cart_recommendation",
            variant_id: selectedVariantId,
            quantity: selectedQuantity
          }
        });

        // Store attribution data in cart attributes for order processing
        await window.analyticsApi.storeCartAttribution({
          session_id: sessionId,
          product_id: productId,
          extension_type: "phoenix",
          context: context,
          position: position,
          timestamp: new Date().toISOString()
        });
      }

      // Restore button state
      addToCartButton.disabled = false;
      addToCartButton.style.cursor = 'pointer';
      addToCartButton.textContent = originalButtonText;

      // Show success feedback
      this.showSuccessMessage('Product added to cart!');

      // Trigger multiple cart update events for different themes
      if (typeof window.dispatchEvent === 'function') {
        // Standard Shopify events
        window.dispatchEvent(new CustomEvent('cart:updated'));
        window.dispatchEvent(new CustomEvent('cart:refresh'));
        window.dispatchEvent(new CustomEvent('cart:updated', { detail: { cart: response } }));

        // Theme-specific events
        window.dispatchEvent(new CustomEvent('cartUpdated'));
        window.dispatchEvent(new CustomEvent('cart:build'));
        window.dispatchEvent(new CustomEvent('cart:change'));

        // Additional events for better theme compatibility
        window.dispatchEvent(new CustomEvent('cart:add', { detail: { cart: response } }));
        window.dispatchEvent(new CustomEvent('cart:reload'));
        window.dispatchEvent(new CustomEvent('cart:refresh-all'));
      }

      // Try different theme cart refresh methods
      if (typeof window.theme !== 'undefined') {
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
      console.log('🛒 Cart updated via native API:', response);

      // Remove product from recommendations
      this.removeProductFromRecommendations(productId);

      // Force page reload as last resort (commented out for now)
      // setTimeout(() => { window.location.reload(); }, 1000);
    } catch (error) {
      console.error('Error adding to cart:', error);

      // Restore button state on error
      if (addToCartButton) {
        addToCartButton.disabled = false;
        addToCartButton.style.cursor = 'pointer';
        addToCartButton.textContent = originalButtonText;
      }

      this.showErrorMessage('Failed to add product to cart');
    }
  }

  // Remove product from recommendations after adding to cart
  removeProductFromRecommendations(productId) {
    const swiperWrapper = document.querySelector('.swiper-wrapper');
    if (!swiperWrapper) return;

    // Find the product slide
    const productSlides = swiperWrapper.querySelectorAll('.swiper-slide');
    let targetSlide = null;

    productSlides.forEach(slide => {
      const productCard = slide.querySelector('.product-card');
      if (productCard && productCard.onclick && productCard.onclick.toString().includes(productId)) {
        targetSlide = slide;
      }
    });

    if (targetSlide) {
      // Add fade out animation
      targetSlide.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      targetSlide.style.opacity = '0';
      targetSlide.style.transform = 'scale(0.8)';

      // Remove after animation
      setTimeout(() => {
        targetSlide.remove();
        console.log(`🗑️ Removed product ${productId} from recommendations`);

        // Update Swiper with remaining slides
        if (window.swiper) {
          window.swiper.update();

          // Disable pagination if only 1 slide left
          const remainingSlides = document.querySelectorAll('.swiper-slide');
          if (remainingSlides.length <= 1) {
            window.swiper.pagination.destroy();
            document.querySelector('.swiper-pagination').style.display = 'none';
          }
        }
      }, 300);
    }
  }

  // Handle shop now with analytics tracking
  handleShopNow(productId, position, productUrl, sessionId) {
    if (window.analyticsApi && sessionId) {
      // Track shop now interaction
      window.analyticsApi.trackInteraction({
        session_id: sessionId,
        product_id: productId,
        interaction_type: "shop_now",
        position: position,
        extension_type: "phoenix",
        context: "cart",
        metadata: { source: "cart_recommendation" }
      }).catch(error => {
        console.error('Failed to track shop now click:', error);
      });
    }

    // Navigate to product page with attribution
    if (productUrl && window.analyticsApi && sessionId) {
      const urlWithAttribution = window.analyticsApi.addAttributionToUrl(productUrl, productId, position, sessionId);
      window.location.href = urlWithAttribution;
    } else if (productUrl) {
      window.location.href = productUrl;
    }
  }
}

// Export for use in other files
window.ProductCardManager = ProductCardManager;

// Create global instance for use in HTML onclick handlers
window.productCardManager = new ProductCardManager();
