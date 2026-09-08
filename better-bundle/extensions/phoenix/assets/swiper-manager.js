/**
 * SwiperManager - Handles Swiper carousel initialization and management
 * Optimized for performance with minimal reinitializations
 */
class SwiperManager {
  constructor() {
    this.isUpdatingDropdowns = false;
    this.logger = window.phoenixLogger || console; // Use the global logger with fallback
  }

  // Initialize Swiper
  initializeSwiper() {
    try {
      // Skip Swiper initialization if we're updating dropdowns
      if (this.isUpdatingDropdowns) {
        return;
      }

      if (typeof Swiper !== "undefined") {
        // Always destroy existing Swiper instance if it exists
        if (window.swiper && typeof window.swiper.destroy === 'function') {
          window.swiper.destroy(true, true);
          window.swiper = null;
        }

        // Get slides and viewport info
        const slides = document.querySelectorAll('.swiper-slide');
        const slideCount = slides.length;
        const viewportWidth = window.innerWidth;

        // Determine slides per view based on breakpoints
        let slidesPerView = 1;
        if (viewportWidth >= 1280) slidesPerView = 4;
        else if (viewportWidth >= 1024) slidesPerView = 3;
        else if (viewportWidth >= 640) slidesPerView = 2;
        else slidesPerView = 1;

        // Swiper loop requirements: need at least slidesPerView + 2 slides for proper loop
        const minSlidesForLoop = slidesPerView + 2;
        const shouldLoop = slideCount >= minSlidesForLoop;



        // Swiper is loaded globally from CDN
        window.swiper = new window.Swiper(".swiper", {
          breakpoints: {
            320: { slidesPerView: 1, spaceBetween: 10 },
            640: { slidesPerView: 2, spaceBetween: 12 },
            1024: { slidesPerView: 3, spaceBetween: 15 },
            1280: { slidesPerView: 4, spaceBetween: 18 },
          },
          autoplay: window.swiperConfig?.enable_autoplay
            ? {
              delay: window.swiperConfig.autoplay_delay || 2500,
              disableOnInteraction: true,
              pauseOnMouseEnter: true,
            }
            : false,
          loop: shouldLoop,
          loopAdditionalSlides: 1,
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
              // Prevent navigation clicks from triggering product card clicks
              if (window.productCardManager) {
                window.productCardManager.preventNavigationClickPropagation();
              }
            },
            resize: function () {
              // Recalculate loop when viewport changes
              const currentSlides = document.querySelectorAll('.swiper-slide');
              const currentViewportWidth = window.innerWidth;

              let currentSlidesPerView = 1;
              if (currentViewportWidth >= 1280) currentSlidesPerView = 4;
              else if (currentViewportWidth >= 1024) currentSlidesPerView = 3;
              else if (currentViewportWidth >= 640) currentSlidesPerView = 2;
              else currentSlidesPerView = 1;

              // Use the same proper logic as initialization
              const minSlidesForLoop = currentSlidesPerView + 2;
              const shouldLoopNow = currentSlides.length >= minSlidesForLoop;

              if (this.loop !== shouldLoopNow) {
                this.loop = shouldLoopNow;
                this.update();
              }
            },
          },
        });
      }
    } catch (error) {
      this.logger.error('❌ Swiper initialization failed:', error);
      // Continue without Swiper - variants should still work
    }
  }

  // Prevent navigation arrows from triggering product card clicks
  preventNavigationClickPropagation() {
    const nextButton = document.querySelector('.swiper-button-next');
    const prevButton = document.querySelector('.swiper-button-prev');

    if (nextButton) {
      nextButton.addEventListener('click', (e) => {
        e.stopPropagation();
      });
    }

    if (prevButton) {
      prevButton.addEventListener('click', (e) => {
        e.stopPropagation();
      });
    }
  }

  // Update Swiper when content changes
  updateSwiper() {
    if (this.isUpdatingDropdowns) {
      this.logger.warn('🔄 Skipping Swiper update during dropdown updates');
      return;
    }

    if (!window.swiper || window.swiper.destroyed) {
      this.initializeSwiper();
    } else {
      // Just update the existing Swiper without destroying it
      window.swiper.update();
    }
  }

  // Set dropdown update flag
  setUpdatingDropdowns(updating) {
    this.isUpdatingDropdowns = updating;
  }
}

// Export for use in other files
window.SwiperManager = SwiperManager;
