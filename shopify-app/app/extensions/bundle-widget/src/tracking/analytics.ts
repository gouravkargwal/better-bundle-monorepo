/**
 * Analytics tracking system for bundle widget extension
 * Tracks recommendations, engagement, and purchase attribution
 */

export interface TrackingEvent {
  event_type: string;
  shop_domain: string;
  session_id: string;
  tracking_id: string;
  user_id?: string;
  timestamp: number;
  metadata: Record<string, any>;
}

export interface RecommendationDisplayEvent extends TrackingEvent {
  event_type: 'recommendation_displayed';
  metadata: {
    recommendation_type: 'bundle' | 'individual' | 'popular';
    recommendation_count: number;
    categories: string[];
    position: 'cart' | 'product' | 'collection' | 'homepage';
    page_url: string;
    referrer?: string;
  };
}

export interface RecommendationClickEvent extends TrackingEvent {
  event_type: 'recommendation_clicked';
  metadata: {
    recommendation_type: 'bundle' | 'individual' | 'popular';
    item_id: string;
    item_title: string;
    item_price: number;
    bundle_id?: string;
    position: 'cart' | 'product' | 'collection' | 'homepage';
    click_position: { x: number; y: number };
  };
}

export interface RecommendationAddToCartEvent extends TrackingEvent {
  event_type: 'recommendation_added_to_cart';
  metadata: {
    recommendation_type: 'bundle' | 'individual' | 'popular';
    item_id: string;
    item_title: string;
    item_price: number;
    bundle_id?: string;
    quantity: number;
    cart_total_before: number;
    cart_total_after: number;
  };
}

export interface RecommendationPurchaseEvent extends TrackingEvent {
  event_type: 'recommendation_purchased';
  metadata: {
    recommendation_type: 'bundle' | 'individual' | 'popular';
    item_id: string;
    item_title: string;
    item_price: number;
    bundle_id?: string;
    quantity: number;
    order_id: string;
    order_total: number;
    revenue_attributed: number;
  };
}

export interface WidgetInteractionEvent extends TrackingEvent {
  event_type: 'widget_interaction';
  metadata: {
    interaction_type: 'expand' | 'collapse' | 'filter' | 'sort' | 'search';
    interaction_value?: string;
    time_spent_ms: number;
  };
}

export type TrackingEventUnion = 
  | RecommendationDisplayEvent
  | RecommendationClickEvent
  | RecommendationAddToCartEvent
  | RecommendationPurchaseEvent
  | WidgetInteractionEvent;

class AnalyticsTracker {
  private shopDomain: string;
  private sessionId: string;
  private trackingId: string;
  private userId?: string;
  private eventQueue: TrackingEventUnion[] = [];
  private isProcessing = false;
  private batchSize = 10;
  private flushInterval = 30000; // 30 seconds
  private flushTimer?: NodeJS.Timeout;

  constructor(shopDomain: string) {
    this.shopDomain = shopDomain;
    this.sessionId = this.generateSessionId();
    this.trackingId = this.generateTrackingId();
    this.startPeriodicFlush();
  }

  /**
   * Generate unique session ID for this user session
   */
  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Generate unique tracking ID for this recommendation session
   */
  private generateTrackingId(): string {
    return `track_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Set user ID when available (after login/identification)
   */
  setUserId(userId: string): void {
    this.userId = userId;
  }

  /**
   * Generate new tracking ID for new recommendation sessions
   */
  newTrackingSession(): string {
    this.trackingId = this.generateTrackingId();
    return this.trackingId;
  }

  /**
   * Track recommendation display
   */
  trackRecommendationDisplay(
    recommendationType: 'bundle' | 'individual' | 'popular',
    recommendationCount: number,
    categories: string[],
    position: 'cart' | 'product' | 'collection' | 'homepage',
    pageUrl: string,
    referrer?: string
  ): void {
    const event: RecommendationDisplayEvent = {
      event_type: 'recommendation_displayed',
      shop_domain: this.shopDomain,
      session_id: this.sessionId,
      tracking_id: this.trackingId,
      user_id: this.userId,
      timestamp: Date.now(),
      metadata: {
        recommendation_type: recommendationType,
        recommendation_count: recommendationCount,
        categories,
        position,
        page_url: pageUrl,
        referrer,
      },
    };

    this.queueEvent(event);
  }

  /**
   * Track recommendation click
   */
  trackRecommendationClick(
    recommendationType: 'bundle' | 'individual' | 'popular',
    itemId: string,
    itemTitle: string,
    itemPrice: number,
    bundleId?: string,
    position: 'cart' | 'product' | 'collection' | 'homepage',
    clickPosition: { x: number; y: number }
  ): void {
    const event: RecommendationClickEvent = {
      event_type: 'recommendation_clicked',
      shop_domain: this.shopDomain,
      session_id: this.sessionId,
      tracking_id: this.trackingId,
      user_id: this.userId,
      timestamp: Date.now(),
      metadata: {
        recommendation_type: recommendationType,
        item_id: itemId,
        item_title: itemTitle,
        item_price: itemPrice,
        bundle_id: bundleId,
        position,
        click_position: clickPosition,
      },
    };

    this.queueEvent(event);
  }

  /**
   * Track recommendation added to cart
   */
  trackRecommendationAddToCart(
    recommendationType: 'bundle' | 'individual' | 'popular',
    itemId: string,
    itemTitle: string,
    itemPrice: number,
    bundleId?: string,
    quantity: number,
    cartTotalBefore: number,
    cartTotalAfter: number
  ): void {
    const event: RecommendationAddToCartEvent = {
      event_type: 'recommendation_added_to_cart',
      shop_domain: this.shopDomain,
      session_id: this.sessionId,
      tracking_id: this.trackingId,
      user_id: this.userId,
      timestamp: Date.now(),
      metadata: {
        recommendation_type: recommendationType,
        item_id: itemId,
        item_title: itemTitle,
        item_price: itemPrice,
        bundle_id: bundleId,
        quantity,
        cart_total_before: cartTotalBefore,
        cart_total_after: cartTotalAfter,
      },
    };

    this.queueEvent(event);
  }

  /**
   * Track recommendation purchase (called after order completion)
   */
  trackRecommendationPurchase(
    recommendationType: 'bundle' | 'individual' | 'popular',
    itemId: string,
    itemTitle: string,
    itemPrice: number,
    bundleId?: string,
    quantity: number,
    orderId: string,
    orderTotal: number,
    revenueAttributed: number
  ): void {
    const event: RecommendationPurchaseEvent = {
      event_type: 'recommendation_purchased',
      shop_domain: this.shopDomain,
      session_id: this.sessionId,
      tracking_id: this.trackingId,
      user_id: this.userId,
      timestamp: Date.now(),
      metadata: {
        recommendation_type: recommendationType,
        item_id: itemId,
        item_title: itemTitle,
        item_price: itemPrice,
        bundle_id: bundleId,
        quantity,
        order_id: orderId,
        order_total: orderTotal,
        revenue_attributed: revenueAttributed,
      },
    };

    this.queueEvent(event);
  }

  /**
   * Track widget interactions
   */
  trackWidgetInteraction(
    interactionType: 'expand' | 'collapse' | 'filter' | 'sort' | 'search',
    interactionValue?: string,
    timeSpentMs: number = 0
  ): void {
    const event: WidgetInteractionEvent = {
      event_type: 'widget_interaction',
      shop_domain: this.shopDomain,
      session_id: this.sessionId,
      tracking_id: this.trackingId,
      user_id: this.userId,
      timestamp: Date.now(),
      metadata: {
        interaction_type: interactionType,
        interaction_value: interactionValue,
        time_spent_ms: timeSpentMs,
      },
    };

    this.queueEvent(event);
  }

  /**
   * Queue event for batch processing
   */
  private queueEvent(event: TrackingEventUnion): void {
    this.eventQueue.push(event);
    
    // Flush immediately if queue is full
    if (this.eventQueue.length >= this.batchSize) {
      this.flushEvents();
    }
  }

  /**
   * Start periodic flush timer
   */
  private startPeriodicFlush(): void {
    this.flushTimer = setInterval(() => {
      if (this.eventQueue.length > 0) {
        this.flushEvents();
      }
    }, this.flushInterval);
  }

  /**
   * Flush events to the tracking endpoint
   */
  private async flushEvents(): Promise<void> {
    if (this.isProcessing || this.eventQueue.length === 0) {
      return;
    }

    this.isProcessing = true;
    const eventsToSend = this.eventQueue.splice(0, this.batchSize);

    try {
      await this.sendEvents(eventsToSend);
    } catch (error) {
      console.error('Failed to send tracking events:', error);
      // Re-queue failed events
      this.eventQueue.unshift(...eventsToSend);
    } finally {
      this.isProcessing = false;
    }
  }

  /**
   * Send events to tracking endpoint
   */
  private async sendEvents(events: TrackingEventUnion[]): Promise<void> {
    const response = await fetch('/apps/betterbundle/tracking', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        events,
        shop_domain: this.shopDomain,
        session_id: this.sessionId,
      }),
    });

    if (!response.ok) {
      throw new Error(`Tracking request failed: ${response.status}`);
    }
  }

  /**
   * Get current tracking ID for cart/order attributes
   */
  getCurrentTrackingId(): string {
    return this.trackingId;
  }

  /**
   * Get current session ID
   */
  getCurrentSessionId(): string {
    return this.sessionId;
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    
    // Flush remaining events
    if (this.eventQueue.length > 0) {
      this.flushEvents();
    }
  }
}

// Global tracker instance
let globalTracker: AnalyticsTracker | null = null;

/**
 * Initialize analytics tracker
 */
export function initAnalytics(shopDomain: string): AnalyticsTracker {
  if (globalTracker) {
    globalTracker.destroy();
  }
  
  globalTracker = new AnalyticsTracker(shopDomain);
  return globalTracker;
}

/**
 * Get global analytics tracker
 */
export function getAnalytics(): AnalyticsTracker {
  if (!globalTracker) {
    throw new Error('Analytics not initialized. Call initAnalytics() first.');
  }
  return globalTracker;
}

/**
 * Track recommendation display
 */
export function trackRecommendationDisplay(
  recommendationType: 'bundle' | 'individual' | 'popular',
  recommendationCount: number,
  categories: string[],
  position: 'cart' | 'product' | 'collection' | 'homepage',
  pageUrl: string,
  referrer?: string
): void {
  getAnalytics().trackRecommendationDisplay(
    recommendationType,
    recommendationCount,
    categories,
    position,
    pageUrl,
    referrer
  );
}

/**
 * Track recommendation click
 */
export function trackRecommendationClick(
  recommendationType: 'bundle' | 'individual' | 'popular',
  itemId: string,
  itemTitle: string,
  itemPrice: number,
  bundleId?: string,
  position: 'cart' | 'product' | 'collection' | 'homepage',
  clickPosition: { x: number; y: number }
): void {
  getAnalytics().trackRecommendationClick(
    recommendationType,
    itemId,
    itemTitle,
    itemPrice,
    bundleId,
    position,
    clickPosition
  );
}

/**
 * Track recommendation add to cart
 */
export function trackRecommendationAddToCart(
  recommendationType: 'bundle' | 'individual' | 'popular',
  itemId: string,
  itemTitle: string,
  itemPrice: number,
  bundleId?: string,
  quantity: number,
  cartTotalBefore: number,
  cartTotalAfter: number
): void {
  getAnalytics().trackRecommendationAddToCart(
    recommendationType,
    itemId,
    itemTitle,
    itemPrice,
    bundleId,
    quantity,
    cartTotalBefore,
    cartTotalAfter
  );
}

/**
 * Track widget interaction
 */
export function trackWidgetInteraction(
  interactionType: 'expand' | 'collapse' | 'filter' | 'sort' | 'search',
  interactionValue?: string,
  timeSpentMs: number = 0
): void {
  getAnalytics().trackWidgetInteraction(
    interactionType,
    interactionValue,
    timeSpentMs
  );
}

/**
 * Get current tracking ID for cart attributes
 */
export function getCurrentTrackingId(): string {
  return getAnalytics().getCurrentTrackingId();
}

/**
 * Get current session ID
 */
export function getCurrentSessionId(): string {
  return getAnalytics().getCurrentSessionId();
}

export default AnalyticsTracker;
