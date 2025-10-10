/**
 * ProductImageGallery - Handles image cycling for product cards
 * Lightweight solution that works with existing Swiper carousel
 */
class ProductImageGallery {
  constructor() {
    this.imageStates = new Map(); // Track current image index for each product
    this.init();
  }

  init() {
    // Initialize existing product cards
    this.initializeExistingCards();

    // Watch for new product cards being added
    this.observeNewCards();

    // Set up event delegation for image navigation buttons
    this.setupEventDelegation();
  }

  setupEventDelegation() {
    // Handle clicks on the image itself (for mobile/desktop)
    document.addEventListener('click', (e) => {
      if (e.target && e.target.classList && e.target.classList.contains('product-card__image')) {
        const productCard = e.target.closest && e.target.closest('.product-card');
        if (productCard && productCard.dataset.images) {
          try {
            const images = JSON.parse(productCard.dataset.images);
            if (images && images.length > 1) {
              e.preventDefault();
              e.stopPropagation();
              this.nextImage(productCard);
            }
          } catch (error) {
            // If parsing fails, let the original click handler work
          }
        }
      }

      // Resume autoplay when clicking anywhere (as a fallback)
      if (window.swiper && window.swiper.autoplay) {
        setTimeout(() => {
          if (window.swiper && window.swiper.autoplay) {
            window.swiper.autoplay.resume();
          }
        }, 200);
      }
    });

    // Pause Swiper autoplay only when user is actively interacting with image gallery
    document.addEventListener('mouseenter', (e) => {
      if (e.target && e.target.closest && e.target.closest('.product-card__image-container')) {
        const productCard = e.target.closest('.product-card');
        if (productCard && productCard.dataset.images) {
          try {
            const images = JSON.parse(productCard.dataset.images);
            if (images && images.length > 1 && window.swiper && window.swiper.autoplay) {
              window.swiper.autoplay.pause();
            }
          } catch (error) {
            // Ignore parsing errors
          }
        }
      }
    }, true);

    // Resume Swiper autoplay when leaving the image container
    document.addEventListener('mouseleave', (e) => {
      if (e.target && e.target.closest && e.target.closest('.product-card__image-container')) {
        const productCard = e.target.closest('.product-card');
        if (productCard && productCard.dataset.images) {
          try {
            const images = JSON.parse(productCard.dataset.images);
            if (images && images.length > 1 && window.swiper && window.swiper.autoplay) {
              // Small delay to ensure smooth transition
              setTimeout(() => {
                if (window.swiper && window.swiper.autoplay) {
                  window.swiper.autoplay.resume();
                }
              }, 100);
            }
          } catch (error) {
            // Ignore parsing errors
          }
        }
      }
    }, true);
  }

  initializeExistingCards() {
    const productCards = document.querySelectorAll('.product-card[data-images]');
    productCards.forEach(card => this.initializeCard(card));
  }

  initializeCard(productCard) {
    const productId = productCard.dataset.productId;
    const imagesData = productCard.dataset.images;

    if (!imagesData) return;

    try {
      const images = JSON.parse(imagesData);
      if (!images || images.length <= 1) return;

      // Initialize image state
      this.imageStates.set(productId, 0);

      // Add touch support for mobile
      this.addTouchSupport(productCard);

      console.log(`🖼️ Initialized image gallery for product ${productId} with ${images.length} images`);
    } catch (error) {
      console.warn('Failed to parse images data:', error);
    }
  }

  addTouchSupport(productCard) {
    const imageContainer = productCard.querySelector('.product-card__image-container');
    if (!imageContainer) return;

    let touchStartX = 0;
    let touchStartY = 0;
    let touchEndX = 0;
    let touchEndY = 0;

    imageContainer.addEventListener('touchstart', (e) => {
      touchStartX = e.changedTouches[0].screenX;
      touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    imageContainer.addEventListener('touchend', (e) => {
      touchEndX = e.changedTouches[0].screenX;
      touchEndY = e.changedTouches[0].screenY;

      const deltaX = touchEndX - touchStartX;
      const deltaY = touchEndY - touchStartY;

      // Only handle horizontal swipes (ignore vertical scrolling)
      if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
        e.preventDefault();
        if (deltaX > 0) {
          this.previousImage(productCard);
        } else {
          this.nextImage(productCard);
        }
      }
    }, { passive: false });
  }

  observeNewCards() {
    // Watch for new product cards being added to the DOM
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            // Check if the added node is a product card
            if (node.classList && node.classList.contains('product-card')) {
              this.initializeCard(node);
            }

            // Check for product cards within the added node
            const productCards = node.querySelectorAll ? node.querySelectorAll('.product-card[data-images]') : [];
            productCards.forEach(card => this.initializeCard(card));
          }
        });
      });
    });

    // Observe the swiper wrapper for new slides
    const swiperWrapper = document.querySelector('.swiper-wrapper');
    if (swiperWrapper) {
      observer.observe(swiperWrapper, { childList: true, subtree: true });
    }
  }

  nextImage(productCard) {
    const productId = productCard.dataset.productId;
    const imagesData = productCard.dataset.images;

    if (!imagesData) return;

    try {
      const images = JSON.parse(imagesData);
      if (!images || images.length <= 1) return;

      const currentIndex = this.imageStates.get(productId) || 0;
      const nextIndex = (currentIndex + 1) % images.length;

      this.switchToImage(productCard, images, nextIndex);
      this.imageStates.set(productId, nextIndex);

    } catch (error) {
      console.warn('Failed to switch image:', error);
    }
  }

  previousImage(productCard) {
    const productId = productCard.dataset.productId;
    const imagesData = productCard.dataset.images;

    if (!imagesData) return;

    try {
      const images = JSON.parse(imagesData);
      if (!images || images.length <= 1) return;

      const currentIndex = this.imageStates.get(productId) || 0;
      const prevIndex = currentIndex === 0 ? images.length - 1 : currentIndex - 1;

      this.switchToImage(productCard, images, prevIndex);
      this.imageStates.set(productId, prevIndex);

    } catch (error) {
      console.warn('Failed to switch image:', error);
    }
  }

  switchToImage(productCard, images, index) {
    const imageElement = productCard.querySelector('.product-card__image');
    if (!imageElement || !images[index]) return;

    // Smooth transition
    imageElement.style.opacity = '0.7';

    setTimeout(() => {
      imageElement.src = images[index].url;
      imageElement.alt = images[index].alt_text || images[index].alt || 'Product image';
      imageElement.style.opacity = '1';

      // Ensure autoplay resumes after image switch with a longer delay
      setTimeout(() => {
        if (window.swiper && window.swiper.autoplay) {
          window.swiper.autoplay.resume();
        }
      }, 500);
    }, 150);
  }

  // Public method for external calls (like from onclick handlers)
  nextImagePublic(productCard) {
    this.nextImage(productCard);
  }

  // Reset image state for a product (useful when product data changes)
  resetProduct(productId) {
    this.imageStates.delete(productId);
  }
}

// Initialize immediately and ensure it's available globally
window.productImageGallery = new ProductImageGallery();

// Also initialize when DOM is ready as backup
document.addEventListener('DOMContentLoaded', () => {
  if (!window.productImageGallery) {
    window.productImageGallery = new ProductImageGallery();
  }
});
