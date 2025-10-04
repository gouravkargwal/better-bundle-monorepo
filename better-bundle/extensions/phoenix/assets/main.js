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
    this.api = window.RecommendationAPI ? new window.RecommendationAPI() : null;
    this.cardManager = window.productCardManager; // Use global instance
    this.analyticsApi = window.analyticsApi;
    this.config = this.getConfig();
    this.sessionId = window.sessionId; // Use session ID from Liquid template

    console.log('🔧 Phoenix RecommendationCarousel initialized:', {
      hasApi: !!this.api,
      hasCardManager: !!this.cardManager,
      hasAnalyticsApi: !!this.analyticsApi,
      hasSessionId: !!this.sessionId,
      config: this.config
    });
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
      context: window.context || 'cart' // Dynamic context from Liquid template
    };
  }

  // Initialize the recommendation carousel
  async init() {
    try {
      console.log('🚀 Phoenix: Starting carousel initialization...');

      // Set global swiper config for product card manager
      window.swiperConfig = {
        enable_autoplay: this.config.enableAutoplay,
        autoplay_delay: this.config.autoplayDelay,
        show_arrows: this.config.showArrows,
        show_pagination: this.config.showPagination
      };

      // Set up timeout to prevent infinite loading
      const loadingTimeout = setTimeout(() => {
        console.warn('⏰ Phoenix: Loading timeout reached, hiding carousel');
        this.hideCarousel();
      }, 10000); // 10 second timeout

      // Get or create session ID from analytics API
      let sessionId;
      if (this.analyticsApi && this.config.shopDomain) {
        try {
          console.log('🔍 Phoenix: Attempting to get session from analytics API...');
          sessionId = await this.analyticsApi.getOrCreateSession(
            this.config.shopDomain,
            this.config.customerId ? String(this.config.customerId) : undefined
          );
          console.log('✅ Phoenix: Session ID obtained from analytics API:', sessionId);
        } catch (error) {
          console.error('❌ Phoenix: Failed to get session from analytics API:', error);
          clearTimeout(loadingTimeout);
          this.hideCarousel();
          return;
        }
      } else {
        console.error('❌ Phoenix: Analytics API not available');
        clearTimeout(loadingTimeout);
        this.hideCarousel();
        return;
      }

      // Show skeleton loading before API call
      if (window.productCardManager) {
        console.log('🔄 Phoenix: Showing skeleton loading...');
        window.productCardManager.showSkeletonLoading();

        // Debug: Check if skeleton elements are created
        setTimeout(() => {
          const skeletonElements = document.querySelectorAll('.loading-skeleton');
          console.log('🔍 Phoenix: Skeleton elements found:', skeletonElements.length);
          if (skeletonElements.length > 0) {
            console.log('✅ Phoenix: Skeleton animation should be visible');
          } else {
            console.warn('⚠️ Phoenix: No skeleton elements found');
          }
        }, 100);
      } else {
        console.error('❌ Phoenix: ProductCardManager not available');
      }

      // Fetch recommendations with timeout
      console.log('🌐 Phoenix: Fetching recommendations...');
      const recommendations = await this.api.fetchRecommendations(
        this.config.productIds,
        this.config.customerId ? String(this.config.customerId) : undefined,
        this.config.limit
      );

      // Clear timeout since we got a response
      clearTimeout(loadingTimeout);

      if (recommendations && recommendations.length > 0) {
        console.log('✅ Phoenix: Received recommendations, updating cards...');

        // Clear global fallback timeout since we successfully loaded recommendations
        if (window.globalFallbackTimeout) {
          clearTimeout(window.globalFallbackTimeout);
          console.log('✅ Phoenix: Cleared global fallback timeout');
        }

        const productIds = recommendations.map((product) => product.id);

        if (this.analyticsApi) {
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
            console.error('❌ Phoenix: Failed to track recommendation view:', error);
            // Don't fail the entire flow for tracking errors
          }
        } else {
          console.warn('⚠️ Phoenix: Analytics API not available, skipping recommendation tracking');
        }

        // Update product cards with real recommendations and analytics tracking
        this.cardManager.updateProductCards(recommendations, this.analyticsApi, sessionId, this.config.context);
      } else {
        console.log('❌ Phoenix: No recommendations available, hiding carousel');
        this.hideCarousel();
      }
    } catch (error) {
      console.error('❌ Phoenix: Carousel initialization failed:', error);
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
document.addEventListener('DOMContentLoaded', function () {
  try {
    console.log('Phoenix: DOMContentLoaded');

    // Global fallback timeout to prevent infinite skeleton loading
    const globalFallbackTimeout = setTimeout(() => {
      console.warn('⏰ Phoenix: Global fallback timeout - hiding carousel after 15 seconds');
      const carouselContainer = document.querySelector('.shopify-app-block');
      if (carouselContainer) {
        // Only hide if carousel is still in skeleton loading state
        const skeletonElements = carouselContainer.querySelectorAll('.loading-skeleton');
        if (skeletonElements.length > 0) {
          console.log('⚠️ Phoenix: Hiding carousel due to timeout - skeleton still visible');
          carouselContainer.style.display = 'none';
        } else {
          console.log('✅ Phoenix: Carousel already loaded successfully, not hiding');
        }
      }
    }, 15000); // 15 second global timeout

    // Store global timeout reference for clearing
    window.globalFallbackTimeout = globalFallbackTimeout;

    // Global variables are now initialized in the Liquid template
    // Initialize Swiper for both design and live mode
    if (window.designMode) {
      console.log('Design mode detected - initializing Swiper with dummy data');
      clearTimeout(globalFallbackTimeout); // Clear timeout in design mode
      console.log('✅ Phoenix: Cleared global fallback timeout in design mode');

      // Initialize Swiper for design mode (dummy data already in HTML)
      window.swiperConfig = {
        enable_autoplay: window.enableAutoplay,
        autoplay_delay: window.autoplayDelay,
        show_arrows: window.showArrows,
        show_pagination: window.showPagination
      };

      // Initialize Swiper for design mode
      const swiper = new window.Swiper('.swiper', {
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
      });

      window.swiper = swiper;
    } else {
      // Initialize Swiper for skeleton loading in live mode
      console.log('Live mode detected - initializing Swiper for skeleton loading');
      window.swiperConfig = {
        enable_autoplay: window.enableAutoplay,
        autoplay_delay: window.autoplayDelay,
        show_arrows: window.showArrows,
        show_pagination: window.showPagination
      };

      // Initialize Swiper for skeleton loading
      const swiper = new window.Swiper('.swiper', {
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
      });

      window.swiper = swiper;

      // Initialize the carousel for live mode
      const carousel = new RecommendationCarousel();
      window.recommendationCarousel = carousel;

      // Initialize when page loads
      carousel.init();
    }
  }
  catch (error) {
    console.error('❌ Phoenix: Failed to initialize carousel:', error);
    // Clear global timeout on error
    const carouselContainer = document.querySelector('.shopify-app-block');
    if (carouselContainer) {
      carouselContainer.style.display = 'none';
    }
  }
});

// Export for global access
window.RecommendationCarousel = RecommendationCarousel;