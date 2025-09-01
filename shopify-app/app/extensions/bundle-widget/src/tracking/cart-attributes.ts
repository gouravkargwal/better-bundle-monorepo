/**
 * Cart attribute manager for tracking recommendation attribution
 * Appends tracking IDs to cart attributes, note attributes, and line items
 */

export interface CartAttributeData {
  tracking_id: string;
  session_id: string;
  recommendation_type: 'bundle' | 'individual' | 'popular';
  bundle_id?: string;
  item_id: string;
  item_title: string;
  item_price: number;
  quantity: number;
  timestamp: number;
  shop_domain: string;
}

export interface CartNoteData {
  tracking_id: string;
  session_id: string;
  recommendation_count: number;
  total_recommendations_value: number;
  timestamp: number;
}

export interface LineItemAttributeData {
  tracking_id: string;
  session_id: string;
  recommendation_type: 'bundle' | 'individual' | 'popular';
  bundle_id?: string;
  position: 'cart' | 'product' | 'collection' | 'homepage';
  click_position?: { x: number; y: number };
  timestamp: number;
}

class CartAttributeManager {
  private shopDomain: string;
  private currentTrackingId: string;
  private currentSessionId: string;

  constructor(shopDomain: string, trackingId: string, sessionId: string) {
    this.shopDomain = shopDomain;
    this.currentTrackingId = trackingId;
    this.currentSessionId = sessionId;
  }

  /**
   * Update tracking IDs
   */
  updateTrackingIds(trackingId: string, sessionId: string): void {
    this.currentTrackingId = trackingId;
    this.currentSessionId = sessionId;
  }

  /**
   * Generate cart attributes for a recommendation
   */
  generateCartAttributes(
    recommendationType: 'bundle' | 'individual' | 'popular',
    itemId: string,
    itemTitle: string,
    itemPrice: number,
    bundleId?: string,
    quantity: number = 1
  ): CartAttributeData {
    return {
      tracking_id: this.currentTrackingId,
      session_id: this.currentSessionId,
      recommendation_type: recommendationType,
      bundle_id: bundleId,
      item_id: itemId,
      item_title: itemTitle,
      item_price: itemPrice,
      quantity,
      timestamp: Date.now(),
      shop_domain: this.shopDomain,
    };
  }

  /**
   * Generate cart note attributes
   */
  generateCartNoteAttributes(
    recommendationCount: number,
    totalRecommendationsValue: number
  ): CartNoteData {
    return {
      tracking_id: this.currentTrackingId,
      session_id: this.currentSessionId,
      recommendation_count: recommendationCount,
      total_recommendations_value: totalRecommendationsValue,
      timestamp: Date.now(),
    };
  }

  /**
   * Generate line item attributes
   */
  generateLineItemAttributes(
    recommendationType: 'bundle' | 'individual' | 'popular',
    bundleId?: string,
    position: 'cart' | 'product' | 'collection' | 'homepage' = 'cart',
    clickPosition?: { x: number; y: number }
  ): LineItemAttributeData {
    return {
      tracking_id: this.currentTrackingId,
      session_id: this.currentSessionId,
      recommendation_type: recommendationType,
      bundle_id: bundleId,
      position,
      click_position: clickPosition,
      timestamp: Date.now(),
    };
  }

  /**
   * Format cart attributes for Shopify API
   */
  formatCartAttributesForShopify(attributes: CartAttributeData): Record<string, string> {
    return {
      [`_betterbundle_tracking_id`]: attributes.tracking_id,
      [`_betterbundle_session_id`]: attributes.session_id,
      [`_betterbundle_recommendation_type`]: attributes.recommendation_type,
      [`_betterbundle_bundle_id`]: attributes.bundle_id || '',
      [`_betterbundle_item_id`]: attributes.item_id,
      [`_betterbundle_item_title`]: attributes.item_title,
      [`_betterbundle_item_price`]: attributes.item_price.toString(),
      [`_betterbundle_quantity`]: attributes.quantity.toString(),
      [`_betterbundle_timestamp`]: attributes.timestamp.toString(),
      [`_betterbundle_shop_domain`]: attributes.shop_domain,
    };
  }

  /**
   * Format cart note attributes for Shopify API
   */
  formatCartNoteAttributesForShopify(attributes: CartNoteData): Record<string, string> {
    return {
      [`_betterbundle_note_tracking_id`]: attributes.tracking_id,
      [`_betterbundle_note_session_id`]: attributes.session_id,
      [`_betterbundle_note_recommendation_count`]: attributes.recommendation_count.toString(),
      [`_betterbundle_note_total_value`]: attributes.total_recommendations_value.toString(),
      [`_betterbundle_note_timestamp`]: attributes.timestamp.toString(),
    };
  }

  /**
   * Format line item attributes for Shopify API
   */
  formatLineItemAttributesForShopify(attributes: LineItemAttributeData): Record<string, string> {
    const lineItemAttrs: Record<string, string> = {
      [`_betterbundle_line_tracking_id`]: attributes.tracking_id,
      [`_betterbundle_line_session_id`]: attributes.session_id,
      [`_betterbundle_line_recommendation_type`]: attributes.recommendation_type,
      [`_betterbundle_line_position`]: attributes.position,
      [`_betterbundle_line_timestamp`]: attributes.timestamp.toString(),
    };

    if (attributes.bundle_id) {
      lineItemAttrs[`_betterbundle_line_bundle_id`] = attributes.bundle_id;
    }

    if (attributes.click_position) {
      lineItemAttrs[`_betterbundle_line_click_x`] = attributes.click_position.x.toString();
      lineItemAttrs[`_betterbundle_line_click_y`] = attributes.click_position.y.toString();
    }

    return lineItemAttrs;
  }

  /**
   * Parse cart attributes from Shopify API response
   */
  parseCartAttributesFromShopify(shopifyAttributes: Record<string, any>): CartAttributeData | null {
    const trackingId = shopifyAttributes['_betterbundle_tracking_id'];
    if (!trackingId) return null;

    return {
      tracking_id: trackingId,
      session_id: shopifyAttributes['_betterbundle_session_id'] || '',
      recommendation_type: shopifyAttributes['_betterbundle_recommendation_type'] || 'individual',
      bundle_id: shopifyAttributes['_betterbundle_bundle_id'] || undefined,
      item_id: shopifyAttributes['_betterbundle_item_id'] || '',
      item_title: shopifyAttributes['_betterbundle_item_title'] || '',
      item_price: parseFloat(shopifyAttributes['_betterbundle_item_price'] || '0'),
      quantity: parseInt(shopifyAttributes['_betterbundle_quantity'] || '1'),
      timestamp: parseInt(shopifyAttributes['_betterbundle_timestamp'] || '0'),
      shop_domain: shopifyAttributes['_betterbundle_shop_domain'] || '',
    };
  }

  /**
   * Parse cart note attributes from Shopify API response
   */
  parseCartNoteAttributesFromShopify(shopifyAttributes: Record<string, any>): CartNoteData | null {
    const trackingId = shopifyAttributes['_betterbundle_note_tracking_id'];
    if (!trackingId) return null;

    return {
      tracking_id: trackingId,
      session_id: shopifyAttributes['_betterbundle_note_session_id'] || '',
      recommendation_count: parseInt(shopifyAttributes['_betterbundle_note_recommendation_count'] || '0'),
      total_recommendations_value: parseFloat(shopifyAttributes['_betterbundle_note_total_value'] || '0'),
      timestamp: parseInt(shopifyAttributes['_betterbundle_note_timestamp'] || '0'),
    };
  }

  /**
   * Parse line item attributes from Shopify API response
   */
  parseLineItemAttributesFromShopify(shopifyAttributes: Record<string, any>): LineItemAttributeData | null {
    const trackingId = shopifyAttributes['_betterbundle_line_tracking_id'];
    if (!trackingId) return null;

    const attributes: LineItemAttributeData = {
      tracking_id: trackingId,
      session_id: shopifyAttributes['_betterbundle_line_session_id'] || '',
      recommendation_type: shopifyAttributes['_betterbundle_line_recommendation_type'] || 'individual',
      position: shopifyAttributes['_betterbundle_line_position'] || 'cart',
      timestamp: parseInt(shopifyAttributes['_betterbundle_line_timestamp'] || '0'),
    };

    if (shopifyAttributes['_betterbundle_line_bundle_id']) {
      attributes.bundle_id = shopifyAttributes['_betterbundle_line_bundle_id'];
    }

    if (shopifyAttributes['_betterbundle_line_click_x'] && shopifyAttributes['_betterbundle_line_click_y']) {
      attributes.click_position = {
        x: parseInt(shopifyAttributes['_betterbundle_line_click_x']),
        y: parseInt(shopifyAttributes['_betterbundle_line_click_y']),
      };
    }

    return attributes;
  }

  /**
   * Generate cart attributes JSON for cart note
   */
  generateCartNoteJson(
    recommendationCount: number,
    totalRecommendationsValue: number
  ): string {
    const noteData = this.generateCartNoteAttributes(recommendationCount, totalRecommendationsValue);
    return JSON.stringify(noteData);
  }

  /**
   * Generate line item attributes JSON
   */
  generateLineItemAttributesJson(
    recommendationType: 'bundle' | 'individual' | 'popular',
    bundleId?: string,
    position: 'cart' | 'product' | 'collection' | 'homepage' = 'cart',
    clickPosition?: { x: number; y: number }
  ): string {
    const lineItemData = this.generateLineItemAttributes(
      recommendationType,
      bundleId,
      position,
      clickPosition
    );
    return JSON.stringify(lineItemData);
  }

  /**
   * Check if cart has tracking attributes
   */
  hasTrackingAttributes(shopifyAttributes: Record<string, any>): boolean {
    return !!shopifyAttributes['_betterbundle_tracking_id'];
  }

  /**
   * Check if line item has tracking attributes
   */
  hasLineItemTrackingAttributes(shopifyAttributes: Record<string, any>): boolean {
    return !!shopifyAttributes['_betterbundle_line_tracking_id'];
  }

  /**
   * Get all tracking attributes from cart
   */
  getAllTrackingAttributes(shopifyAttributes: Record<string, any>): {
    cart: CartAttributeData | null;
    note: CartNoteData | null;
  } {
    return {
      cart: this.parseCartAttributesFromShopify(shopifyAttributes),
      note: this.parseCartNoteAttributesFromShopify(shopifyAttributes),
    };
  }

  /**
   * Get tracking attributes from line item
   */
  getLineItemTrackingAttributes(shopifyAttributes: Record<string, any>): LineItemAttributeData | null {
    return this.parseLineItemAttributesFromShopify(shopifyAttributes);
  }

  /**
   * Generate summary of all tracking data
   */
  generateTrackingSummary(
    cartAttributes: CartAttributeData[],
    noteAttributes: CartNoteData | null
  ): {
    total_recommendations: number;
    total_value: number;
    recommendation_types: Record<string, number>;
    bundle_ids: string[];
    session_ids: string[];
    tracking_ids: string[];
  } {
    const summary = {
      total_recommendations: 0,
      total_value: 0,
      recommendation_types: {} as Record<string, number>,
      bundle_ids: [] as string[],
      session_ids: [] as string[],
      tracking_ids: [] as string[],
    };

    // Process cart attributes
    cartAttributes.forEach(attr => {
      summary.total_recommendations += attr.quantity;
      summary.total_value += attr.item_price * attr.quantity;
      
      summary.recommendation_types[attr.recommendation_type] = 
        (summary.recommendation_types[attr.recommendation_type] || 0) + attr.quantity;
      
      if (attr.bundle_id && !summary.bundle_ids.includes(attr.bundle_id)) {
        summary.bundle_ids.push(attr.bundle_id);
      }
      
      if (!summary.session_ids.includes(attr.session_id)) {
        summary.session_ids.push(attr.session_id);
      }
      
      if (!summary.tracking_ids.includes(attr.tracking_id)) {
        summary.tracking_ids.push(attr.tracking_id);
      }
    });

    // Add note attributes if available
    if (noteAttributes) {
      summary.total_recommendations += noteAttributes.recommendation_count;
      summary.total_value += noteAttributes.total_recommendations_value;
    }

    return summary;
  }
}

export default CartAttributeManager;
