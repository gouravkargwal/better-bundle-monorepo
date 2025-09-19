// Main initialization and coordination

// Extension Activity Tracker
class PhoenixExtensionTracker {
  constructor(shopDomain, baseUrl) {
    this.shopDomain = shopDomain;
    this.baseUrl = baseUrl;
    this.extensionUid = 'ebf2bbf3-ac07-95dc-4552-0633f958c425ea14e806';
    this.lastReported = localStorage.getItem(`ext_${this.extensionUid}_last_reported`);
  }

  async trackLoad() {
    try {
      const now = Date.now();
      const lastReportedKey = `ext_${this.extensionUid}_last_reported`;
      const lastReportedValue = localStorage.getItem(lastReportedKey);
      const lastReported = lastReportedValue ? parseInt(lastReportedValue) : null;

      console.log(`[Phoenix Tracker] localStorage debug:`, {
        key: lastReportedKey,
        rawValue: lastReportedValue,
        parsedValue: lastReported,
        allKeys: Object.keys(localStorage)
      });

      const hoursSinceLastReport = lastReported ? (now - lastReported) / (1000 * 60 * 60) : Infinity;

      console.log(`[Phoenix Tracker] Time comparison debug:`, {
        currentTime: now,
        currentTimeISO: new Date(now).toISOString(),
        lastReportedTime: lastReported,
        lastReportedISO: lastReported ? new Date(lastReported).toISOString() : "Never",
        timeDifference: lastReported ? now - lastReported : "N/A",
        timeDifferenceHours: lastReported ? (now - lastReported) / (1000 * 60 * 60) : "N/A",
        hoursSinceLastReport: lastReported ? hoursSinceLastReport.toFixed(2) : "Never reported",
        shouldReport: !lastReported || hoursSinceLastReport > 24,
      });

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
        await this.reportToAPI(this.shopDomain);
        localStorage.setItem(lastReportedKey, now.toString());
        console.log(`[Phoenix Tracker] Updated last reported timestamp:`, {
          key: lastReportedKey,
          value: now.toString(),
          timestamp: new Date(now).toISOString()
        });

        // Verify the save worked
        const savedValue = localStorage.getItem(lastReportedKey);
        console.log(`[Phoenix Tracker] Verification - saved value:`, savedValue);
      } else {
        console.log(`[Phoenix Tracker] Skipping report (reported ${hoursSinceLastReport.toFixed(2)} hours ago)`);
      }
    } catch (error) {
      console.error(`[Phoenix Tracker] Error in trackLoad:`, error);
      throw error;
    }
  }

  async reportToAPI() {
    try {
      const requestBody = {
        extension_type: 'phoenix',
        extension_uid: this.extensionUid,
        page_url: window.location?.href || 'unknown',
        app_block_target: 'theme_app_extension',
        app_block_location: 'Theme Extension',
        shop_domain: this.shopDomain
      };


      const response = await fetch(`${this.baseUrl}/extension-activity/track-load`, {
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
      throw error;
    }
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
      // Track extension activity
      if (this.config.shopDomain) {
        const tracker = new PhoenixExtensionTracker(this.config.shopDomain, this.analyticsApi?.baseUrl);
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

      // Show skeleton only when API call starts
      this.showSkeleton();

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
          this.hideSkeleton();
          this.hideCarousel();
          return;
        }
      } else {
        console.error('❌ Phoenix: Analytics API not available');
        this.hideSkeleton();
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
        this.hideSkeleton();
        this.hideCarousel();
      }
    } catch (error) {
      this.hideSkeleton();
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