class RecommendationCarousel {
  constructor() {
    this.api = new RecommendationAPI();
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
      context: 'cart' // Phoenix extension context
    };
  }

  // Initialize the recommendation carousel
  async init() {
    try {

      // Set global swiper config for product card manager
      window.swiperConfig = {
        enable_autoplay: this.config.enableAutoplay,
        autoplay_delay: this.config.autoplayDelay,
        show_arrows: this.config.showArrows,
        show_pagination: this.config.showPagination
      };

      // Get or create session ID from analytics API
      let sessionId;
      if (this.analyticsApi && this.config.shopDomain) {
        try {
          sessionId = await this.analyticsApi.getOrCreateSession(
            this.config.shopDomain,
            this.config.customerId ? String(this.config.customerId) : undefined
          );
          console.log('✅ Phoenix: Session ID obtained from analytics API:', sessionId);
        } catch (error) {
          console.error('❌ Phoenix: Failed to get session from analytics API:', error);
          this.hideCarousel();
          return;
        }
      } else {
        console.error('❌ Phoenix: Analytics API not available');
        this.hideCarousel();
        return;
      }

      // Fetch recommendations first
      const recommendations = await this.api.fetchRecommendations(
        this.config.productIds,
        this.config.customerId ? String(this.config.customerId) : undefined,
        this.config.limit
      );

      if (recommendations && recommendations.length > 0) {
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
          }
        } else {
          console.warn('⚠️ Phoenix: Analytics API not available, skipping recommendation tracking');
        }

        // Update product cards with real recommendations and analytics tracking
        this.cardManager.updateProductCards(recommendations, this.analyticsApi, sessionId, this.config.context);
      } else {
        this.hideCarousel();
      }
    } catch (error) {
      this.hideCarousel();
    }
  }

  // Show skeleton loading state
  showSkeleton() {
    const skeletonContainer = document.querySelector('.skeleton-container');
    if (skeletonContainer) {
      skeletonContainer.style.display = 'block';
    }
  }

  // Hide skeleton loading state
  hideSkeleton() {
    const skeletonContainer = document.querySelector('.skeleton-container');
    if (skeletonContainer) {
      skeletonContainer.style.display = 'none';
    }
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
    // Global variables are now initialized in the Liquid template
    // Initialize Swiper for both design and live mode
    if (window.designMode) {
      console.log('Design mode detected - initializing Swiper with dummy data');
      // Initialize Swiper for design mode (dummy data already in HTML)
      window.swiperConfig = {
        enable_autoplay: window.enableAutoplay,
        autoplay_delay: window.autoplayDelay,
        show_arrows: window.showArrows,
        show_pagination: window.showPagination
      };

      // Initialize Swiper for design mode
      const swiper = new Swiper('.swiper', {
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
      const swiper = new Swiper('.swiper', {
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
  }
});

// Export for global access
window.RecommendationCarousel = RecommendationCarousel;