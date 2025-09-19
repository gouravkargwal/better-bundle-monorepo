// Main initialization and coordination

// Extension Activity Tracker
class PhoenixExtensionTracker {
  constructor(shopDomain) {
    this.shopDomain = shopDomain;
    this.extensionUid = 'ebf2bbf3-ac07-95dc-4552-0633f958c425ea14e806';
    this.lastReported = localStorage.getItem(`ext_${this.extensionUid}_last_reported`);
  }

  async trackLoad() {
    const now = Date.now();
    const lastReported = this.lastReported ? parseInt(this.lastReported) : null;
    const hoursSinceLastReport = lastReported ? (now - lastReported) / (1000 * 60 * 60) : Infinity;

    console.log(`[Phoenix Tracker] Checking activity tracking:`, {
      shopDomain: this.shopDomain,
      extensionUid: this.extensionUid,
      lastReported: lastReported ? new Date(lastReported).toISOString() : 'Never',
      hoursSinceLastReport: lastReported ? hoursSinceLastReport.toFixed(2) : 'Never reported',
      shouldReport: !lastReported || hoursSinceLastReport > 24
    });

    // Only call API if haven't reported in last 24 hours
    if (!lastReported || hoursSinceLastReport > 24) {
      const timeText = lastReported ? `${hoursSinceLastReport.toFixed(2)} hours ago` : 'never';
      console.log(`[Phoenix Tracker] Reporting activity (last report was ${timeText})`);
      await this.reportToAPI();
      localStorage.setItem(`ext_${this.extensionUid}_last_reported`, now.toString());
      console.log(`[Phoenix Tracker] Updated last reported timestamp`);
    } else {
      console.log(`[Phoenix Tracker] Skipping report (reported ${hoursSinceLastReport.toFixed(2)} hours ago)`);
    }
  }

  async reportToAPI() {
    try {
      const apiBaseUrl = this.getApiBaseUrl();
      const requestBody = {
        extension_type: 'phoenix',
        extension_uid: this.extensionUid,
        page_url: window.location?.href || 'unknown',
        app_block_target: 'theme_app_extension',
        app_block_location: 'Theme Extension'
      };

      console.log(`[Phoenix Tracker] Sending API request:`, {
        url: `${apiBaseUrl}/extension-activity/${this.shopDomain}/track-load`,
        requestBody,
        timestamp: new Date().toISOString()
      });

      const response = await fetch(`${apiBaseUrl}/extension-activity/${this.shopDomain}/track-load`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      console.log(`[Phoenix Tracker] API response:`, {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Phoenix Tracker] API error response:`, errorText);
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const responseData = await response.json();
      console.log(`[Phoenix Tracker] Successfully tracked activity:`, responseData);
    } catch (error) {
      console.error(`[Phoenix Tracker] Failed to track activity:`, {
        error: error.message,
        stack: error.stack,
        shopDomain: this.shopDomain,
        extensionUid: this.extensionUid
      });
    }
  }

  getApiBaseUrl() {
    // Use environment variable or default
    return window.PYTHON_WORKER_URL || 'https://your-api-domain.com/api/v1';
  }
}

// Import classes (they will be available globally after script loading)
// RecommendationAPI and ProductCardManager are loaded from api.js and product-cards.js

class RecommendationCarousel {
  constructor() {
    this.api = new RecommendationAPI();
    this.cardManager = window.productCardManager; // Use global instance
    this.analyticsApi = window.analyticsApi;
    this.config = this.getConfig();
    this.sessionId = this.generateSessionId();
  }

  // Generate unique session ID for analytics tracking
  generateSessionId() {
    return `phoenix_cart_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
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
      console.log('🚀 Initializing recommendation carousel with config:', this.config);
      console.log('🔍 Debug - Global variables:', {
        shopDomain: window.shopDomain,
        customerId: window.customerId,
        cartProductIds: window.cartProductIds,
        designMode: window.designMode
      });

      // Track extension activity
      if (this.config.shopDomain) {
        const tracker = new PhoenixExtensionTracker(this.config.shopDomain);
        tracker.trackLoad().catch((error) => {
          console.warn('Failed to track Phoenix extension activity:', error);
        });
      }

      // Set global swiper config for product card manager
      window.swiperConfig = {
        enable_autoplay: this.config.enableAutoplay,
        autoplay_delay: this.config.autoplayDelay,
        show_arrows: this.config.showArrows,
        show_pagination: this.config.showPagination
      };

      // Fetch recommendations first
      const recommendations = await this.api.fetchRecommendations(
        this.config.productIds,
        this.config.customerId ? String(this.config.customerId) : undefined,
        this.config.limit
      );

      if (recommendations && recommendations.length > 0) {
        // Track recommendation view using unified analytics (single tracking event)
        const productIds = recommendations.map((product) => product.id);

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

        // Update product cards with real recommendations and analytics tracking
        this.cardManager.updateProductCards(recommendations, this.analyticsApi, this.sessionId, this.config.context);
      } else {
        console.log('No recommendations available, hiding carousel');
        // Hide the entire carousel if no recommendations
        this.hideCarousel();
      }
    } catch (error) {
      console.error('Error initializing recommendation carousel:', error);
      console.log('API failed, hiding carousel');
      // Hide the entire carousel if API fails
      this.hideCarousel();
    }
  }

  // Hide the entire carousel when API fails or no recommendations
  hideCarousel() {
    const carouselContainer = document.querySelector('.shopify-app-block');
    if (carouselContainer) {
      carouselContainer.style.display = 'none';
      console.log('Carousel hidden due to API failure or no recommendations');
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
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
});

// Export for global access
window.RecommendationCarousel = RecommendationCarousel;