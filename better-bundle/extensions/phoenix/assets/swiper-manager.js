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
        const slides = document.querySelectorAll('.better-bundle-recommendations .swiper-slide');
        const slideCount = slides.length;
        const viewportWidth = window.innerWidth;

        // Determine slides per view based on breakpoints
        let slidesPerView = 1.2;
        if (viewportWidth >= 1280) slidesPerView = 4;
        else if (viewportWidth >= 1024) slidesPerView = 3;
        else if (viewportWidth >= 640) slidesPerView = 2;

        // Autoplay is desktop-only.
        //
        // On a touch device it competes with the shopper's own scrolling: there
        // is no hover to pause it, the row is the width of the screen, and a
        // card sliding away mid-read is worse than no motion at all. The
        // fractional slidesPerView already signals that the row scrolls, which
        // is the job autoplay was doing badly.
        //
        // Matches the 640px breakpoint below, so "one-and-a-bit cards" and
        // "no autoplay" are the same state.
        const autoplayAllowed =
          Boolean(window.swiperConfig?.enable_autoplay) && viewportWidth >= 640;

        // Loop as soon as there is anything off-screen to scroll to.
        //
        // This asked for slidesPerView + 2, so a shop returning the default 4
        // recommendations got loop:false at the 4-across breakpoint — all four
        // slides visible, nothing to advance to, and autoplay therefore doing
        // nothing at all. It read as "autoplay is broken" when it was really
        // "there is nowhere to go".
        const shouldLoop = slideCount > Math.ceil(slidesPerView);



        // Swiper is loaded globally from CDN
        window.swiper = new window.Swiper(".better-bundle-recommendations .swiper", {
          breakpoints: {
            // Fractional + centred on phones: a sliver of the previous AND the
            // next card is what tells a shopper the row scrolls in both
            // directions, and the arrows are hidden on touch so nothing else
            // says so. A whole-number slidesPerView fills the viewport edge to
            // edge and reads as a static image.
            320: { slidesPerView: 1.2, spaceBetween: 10, centeredSlides: true },
            640: { slidesPerView: 2, spaceBetween: 12, centeredSlides: false },
            1024: { slidesPerView: 3, spaceBetween: 15, centeredSlides: false },
            1280: { slidesPerView: 4, spaceBetween: 18, centeredSlides: false },
          },
          autoplay: autoplayAllowed
            ? {
              delay: window.swiperConfig.autoplay_delay || 2500,
              // false, not true: with `true` the first arrow click stopped
              // autoplay for good, which is indistinguishable from autoplay
              // never having worked.
              disableOnInteraction: false,
              // Mouse only — there is no hover on a touchscreen, so this does
              // nothing on a phone. Touch is handled in `touchStart` below.
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
              nextEl: ".better-bundle-recommendations .swiper-button-next",
              prevEl: ".better-bundle-recommendations .swiper-button-prev",
            }
            : false,
          pagination: window.swiperConfig?.show_pagination
            ? {
              el: ".better-bundle-recommendations .swiper-pagination",
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
            /**
             * Stop autoplay for good on the first touch.
             *
             * `pauseOnMouseEnter` is a mouse feature: a touchscreen has no
             * hover, so on a phone there was nothing holding the carousel still
             * while a shopper read a card — it kept advancing under their thumb.
             *
             * Stopping rather than pausing is the deliberate choice. Someone who
             * has touched the carousel is driving it, and resuming would move
             * the card out from under them a moment later. It also satisfies
             * WCAG 2.2.2 (Pause, Stop, Hide), which wants a way to stop moving
             * content — on desktop that is the hover pause, and this is the
             * touch equivalent.
             */
            touchStart: function () {
              if (this.autoplay && this.autoplay.running) {
                this.autoplay.stop();
              }
            },
            resize: function () {
              // Recalculate loop when viewport changes
              const currentSlides = document.querySelectorAll('.better-bundle-recommendations .swiper-slide');
              const currentViewportWidth = window.innerWidth;

              let currentSlidesPerView = 1.2;
              if (currentViewportWidth >= 1280) currentSlidesPerView = 4;
              else if (currentViewportWidth >= 1024) currentSlidesPerView = 3;
              else if (currentViewportWidth >= 640) currentSlidesPerView = 2;

              if (
                currentViewportWidth < 640 &&
                this.autoplay &&
                this.autoplay.running
              ) {
                this.autoplay.stop();
              }

              const shouldLoopNow =
                currentSlides.length > Math.ceil(currentSlidesPerView);

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
    const nextButton = document.querySelector('.better-bundle-recommendations .swiper-button-next');
    const prevButton = document.querySelector('.better-bundle-recommendations .swiper-button-prev');

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
