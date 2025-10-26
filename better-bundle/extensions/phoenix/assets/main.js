// Load required modules first
// Note: These should be loaded in the correct order in the HTML
// 1. variant-manager.js
// 2. dropdown-manager.js  
// 3. swiper-manager.js
// 4. product-card-renderer.js
// 5. product-cards.js
// 6. main.js

class RecommendationCarousel {
  constructor() {
    this.api = null; // Will be set by main.js with JWT authentication
    this.cardManager = window.productCardManager; // Use global instance
    this.analyticsApi = window.analyticsApi;
    this.config = this.getConfig();
    this.sessionId = window.sessionId; // Use session ID from Liquid template
    this.logger = window.phoenixLogger || console; // Use the global logger with fallback
  }


  // Get configuration from Liquid template
  getConfig() {
    return {
      productIds: window.cartProductIds || [], // Use cart product IDs from Liquid template
      customerId: window.customerId || null,
      shopDomain: window.shopDomain || null,
      enableAutoplay: window.enableAutoplay || true,
      autoplayDelay: window.autoplayDelay || 2500,
      showArrows: window.showArrows || true,
      showPagination: window.showPagination || true,
      limit: window.recommendationLimit || 4,
      context: window.context || 'homepage' // Use context from block system
    };
  }

  // Track recommendation view when user actually views them
  async trackRecommendationView(productIds) {
    if (!this.analyticsApi || !productIds || productIds.length === 0) {
      return;
    }

    try {
      await this.analyticsApi.trackRecommendationView(
        this.config.shopDomain || '',
        this.config.context,
        this.config.customerId ? String(this.config.customerId) : undefined,
        productIds,
        {
          source: 'phoenix_theme_extension',
          cart_product_count: this.config.productIds?.length || 0,
          recommendation_count: productIds.length
        }
      );
    } catch (error) {
      this.logger.error('❌ Phoenix: Failed to track recommendation view:', error);
    }
  }

  // Initialize the recommendation carousel
  async init() {
    try {
      // Check if API is available and JWT is initialized
      if (!this.api) {
        this.logger.error('❌ Phoenix: API not available or JWT not initialized');
        this.hideCarousel();
        return;
      }

      // Set global swiper config for product card manager
      window.swiperConfig = {
        enable_autoplay: this.config.enableAutoplay,
        autoplay_delay: this.config.autoplayDelay,
        show_arrows: this.config.showArrows,
        show_pagination: this.config.showPagination
      };

      // Set up timeout to prevent infinite loading
      const loadingTimeout = setTimeout(() => {
        this.hideCarousel();
      }, 15000); // 15 second timeout

      // Get or create session ID from analytics API with better error handling
      let sessionId;
      if (this.analyticsApi && this.config.shopDomain) {
        try {
          sessionId = await this.analyticsApi.getOrCreateSession(
            this.config.shopDomain,
            this.config.customerId ? String(this.config.customerId) : undefined
          );
        } catch (error) {
          this.logger.error('❌ Phoenix: Failed to get session from analytics API:', error);
          // Try fallback session ID from window or generate one
          sessionId = window.sessionId || `fallback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }
      } else {
        this.logger.warn('⚠️ Phoenix: Analytics API not available, using fallback session');
        sessionId = window.sessionId || `fallback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      }

      // Show skeleton loading before API call
      if (window.productCardManager) {
        window.productCardManager.showSkeletonLoading();
      } else {
        this.logger.error('❌ Phoenix: ProductCardManager not available');
      }

      const recommendations = await this.api.fetchRecommendations(
        this.config.productIds,
        this.config.customerId ? String(this.config.customerId) : undefined,
        this.config.limit
      );

      // Clear timeout since we got a response
      clearTimeout(loadingTimeout);

      if (recommendations && recommendations.length > 0) {

        // Clear global fallback timeout since we successfully loaded recommendations
        if (window.globalFallbackTimeout) {
          clearTimeout(window.globalFallbackTimeout);
        }

        // Update product cards with real recommendations and analytics tracking
        this.cardManager.updateProductCards(recommendations, this.analyticsApi, sessionId, this.config.context, this.trackRecommendationView.bind(this));
      } else {
        this.logger.error('❌ Phoenix: No recommendations available, hiding carousel');
        this.hideCarousel();
      }
    } catch (error) {
      this.logger.error('❌ Phoenix: Carousel initialization failed:', error);
      this.hideCarousel();
    }
  }

  // Show skeleton loading state
  showSkeleton() {
    const skeletonElements = document.querySelectorAll('.loading-skeleton');
    skeletonElements.forEach(element => {
      element.style.display = 'block';
      element.classList.remove('fade-out');
    });
  }

  // Hide skeleton loading state
  hideSkeleton() {
    const skeletonElements = document.querySelectorAll('.loading-skeleton');
    skeletonElements.forEach(element => {
      element.classList.add('fade-out');
      setTimeout(() => {
        element.style.display = 'none';
      }, 300);
    });
  }

  // Hide the entire carousel when API fails or no recommendations
  hideCarousel() {
    const carouselContainer = document.querySelector('.shopify-app-block');
    if (carouselContainer) {
      carouselContainer.style.display = 'none';
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async function () {
  try {
    // Prevent double initialization
    if (window.phoenixInitialized) {
      // Already initialized, skipping
      return;
    }

    // Initialize Phoenix JWT authentication first
    const phoenixJWT = new window.PhoenixJWT();
    await phoenixJWT.initialize();

    // Store Phoenix JWT instance globally
    window.phoenixJWT = phoenixJWT;
    window.phoenixInitialized = true;

    // Global fallback timeout to prevent infinite skeleton loading
    const globalFallbackTimeout = setTimeout(() => {
      const carouselContainer = document.querySelector('.shopify-app-block');
      if (carouselContainer) {
        // Only hide if carousel is still in skeleton loading state
        const skeletonElements = carouselContainer.querySelectorAll('.loading-skeleton');
        if (skeletonElements.length > 0) {
          carouselContainer.style.display = 'none';
        }
      }
    }, 15000); // 15 second global timeout

    // Store global timeout reference for clearing
    window.globalFallbackTimeout = globalFallbackTimeout;

    // Global variables are now initialized in the Liquid template
    // Initialize Swiper for both design and live mode
    if (window.designMode) {
      clearTimeout(globalFallbackTimeout); // Clear timeout in design mode

      // Initialize Swiper for design mode (dummy data already in HTML)
      window.swiperConfig = {
        enable_autoplay: window.enableAutoplay,
        autoplay_delay: window.autoplayDelay,
        show_arrows: window.showArrows,
        show_pagination: window.showPagination
      };

      // Initialize Swiper for design mode with proper horizontal layout
      const swiper = new window.Swiper('.swiper', {
        direction: 'horizontal', // Explicitly set horizontal direction
        slidesPerView: 1,
        spaceBetween: 20,
        loop: true,
        autoplay: window.enableAutoplay ? {
          delay: window.autoplayDelay,
          disableOnInteraction: true,
          pauseOnMouseEnter: true,
        } : false,
        navigation: {
          nextEl: '.swiper-button-next',
          prevEl: '.swiper-button-prev',
        },
        pagination: {
          el: '.swiper-pagination',
          clickable: true,
        },
        breakpoints: {
          640: {
            slidesPerView: 2,
            spaceBetween: 20,
          },
          768: {
            slidesPerView: 3,
            spaceBetween: 20,
          },
          1024: {
            slidesPerView: 4,
            spaceBetween: 20,
          },
        },
        // Ensure proper horizontal layout
        watchSlidesProgress: true,
        watchSlidesVisibility: true,
      });

      window.swiper = swiper;
    } else {
      // Initialize Swiper for skeleton loading in live mode
      window.swiperConfig = {
        enable_autoplay: window.enableAutoplay,
        autoplay_delay: window.autoplayDelay,
        show_arrows: window.showArrows,
        show_pagination: window.showPagination
      };

      // Initialize Swiper for skeleton loading with proper horizontal layout
      const swiper = new window.Swiper('.swiper', {
        direction: 'horizontal', // Explicitly set horizontal direction
        slidesPerView: 1,
        spaceBetween: 20,
        loop: true,
        autoplay: window.enableAutoplay ? {
          delay: window.autoplayDelay,
          disableOnInteraction: true,
          pauseOnMouseEnter: true,
        } : false,
        navigation: {
          nextEl: '.swiper-button-next',
          prevEl: '.swiper-button-prev',
        },
        pagination: {
          el: '.swiper-pagination',
          clickable: true,
        },
        breakpoints: {
          640: {
            slidesPerView: 2,
            spaceBetween: 20,
          },
          768: {
            slidesPerView: 3,
            spaceBetween: 20,
          },
          1024: {
            slidesPerView: 4,
            spaceBetween: 20,
          },
        },
        // Ensure proper horizontal layout
        watchSlidesProgress: true,
        watchSlidesVisibility: true,
      });

      window.swiper = swiper;

      // Initialize the carousel for live mode
      const carousel = new RecommendationCarousel();
      window.recommendationCarousel = carousel;

      // Set up API with JWT authentication
      if (window.RecommendationAPI && window.phoenixJWT) {
        const api = new window.RecommendationAPI();
        api.setPhoenixJWT(window.phoenixJWT);
        carousel.api = api;
      }

      // Set up Analytics API with JWT authentication
      if (window.analyticsApi && window.phoenixJWT) {
        window.analyticsApi.setPhoenixJWT(window.phoenixJWT);
      }

      // Initialize when page loads
      carousel.init();
    }
  }
  catch (error) {
    const logger = window.phoenixLogger || console;
    logger.error('❌ Phoenix: Failed to initialize carousel:', error);
    // Clear global timeout on error
    const carouselContainer = document.querySelector('.shopify-app-block');
    if (carouselContainer) {
      carouselContainer.style.display = 'none';
    }
  }
});

// Export for global access
window.RecommendationCarousel = RecommendationCarousel;