/**
 * Order webhook for tracking revenue attribution and updating billing
 */

import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { performanceBillingService } from "../services/performance-billing.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    // Verify webhook authenticity
    const { admin, session } = await authenticate.webhook(request);
    
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const orderData = await request.json();

    // Extract order information
    const orderId = orderData.id;
    const customerId = orderData.customer?.id;
    const totalPrice = parseFloat(orderData.total_price);
    const lineItems = orderData.line_items || [];
    const noteAttributes = orderData.note_attributes || [];
    const cartAttributes = orderData.cart_attributes || [];

    // Check if order has recommendation tracking
    const hasTracking = checkOrderTracking(noteAttributes, cartAttributes, lineItems);
    
    if (!hasTracking) {
      // No recommendation tracking, skip processing
      return json({ success: true, message: "No recommendation tracking found" });
    }

    // Extract tracking information
    const trackingData = extractTrackingData(noteAttributes, cartAttributes, lineItems);
    
    if (!trackingData) {
      return json({ success: true, message: "Invalid tracking data" });
    }

    // Calculate attributed revenue
    const attributedRevenue = calculateAttributedRevenue(lineItems, trackingData);
    
    if (attributedRevenue <= 0) {
      return json({ success: true, message: "No attributed revenue" });
    }

    // Update shop analytics with attributed revenue
    await updateShopAnalytics(shopDomain, attributedRevenue, orderId);

    // Log the revenue attribution
    await prisma.trackingEvent.create({
      data: {
        shopId: shopDomain,
        eventType: "revenue_attributed",
        sessionId: trackingData.sessionId,
        trackingId: trackingData.trackingId,
        userId: customerId?.toString(),
        timestamp: new Date(),
        metadata: {
          order_id: orderId,
          attributed_revenue: attributedRevenue,
          total_order_value: totalPrice,
          tracking_data: trackingData,
          line_items: lineItems.map(item => ({
            product_id: item.product_id,
            variant_id: item.variant_id,
            quantity: item.quantity,
            price: item.price,
            has_tracking: item.properties?.some((prop: any) => 
              prop.name?.startsWith('_betterbundle_line_')
            )
          }))
        },
        rawEvent: orderData
      }
    });

    console.log(`Revenue attributed: $${attributedRevenue} for order ${orderId} in shop ${shopDomain}`);

    return json({
      success: true,
      attributed_revenue: attributedRevenue,
      order_id: orderId,
      shop_domain: shopDomain
    });

  } catch (error) {
    console.error("Order webhook error:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};

/**
 * Check if order has recommendation tracking
 */
function checkOrderTracking(
  noteAttributes: any[],
  cartAttributes: any[],
  lineItems: any[]
): boolean {
  // Check note attributes
  const hasNoteTracking = noteAttributes.some(attr => 
    attr.name?.startsWith('_betterbundle_note_')
  );

  // Check cart attributes
  const hasCartTracking = cartAttributes.some(attr => 
    attr.name?.startsWith('_betterbundle_')
  );

  // Check line item properties
  const hasLineTracking = lineItems.some(item => 
    item.properties?.some((prop: any) => 
      prop.name?.startsWith('_betterbundle_line_')
    )
  );

  return hasNoteTracking || hasCartTracking || hasLineTracking;
}

/**
 * Extract tracking data from order
 */
function extractTrackingData(
  noteAttributes: any[],
  cartAttributes: any[],
  lineItems: any[]
): {
  trackingId: string;
  sessionId: string;
  recommendationType: string;
  bundleId?: string;
} | null {
  
  // Try to get from note attributes first
  const noteTrackingId = noteAttributes.find(attr => 
    attr.name === '_betterbundle_note_tracking_id'
  )?.value;

  const noteSessionId = noteAttributes.find(attr => 
    attr.name === '_betterbundle_note_session_id'
  )?.value;

  if (noteTrackingId && noteSessionId) {
    return {
      trackingId: noteTrackingId,
      sessionId: noteSessionId,
      recommendationType: 'mixed' // Note attributes indicate mixed recommendations
    };
  }

  // Try to get from cart attributes
  const cartTrackingId = cartAttributes.find(attr => 
    attr.name === '_betterbundle_tracking_id'
  )?.value;

  const cartSessionId = cartAttributes.find(attr => 
    attr.name === '_betterbundle_session_id'
  )?.value;

  if (cartTrackingId && cartSessionId) {
    return {
      trackingId: cartTrackingId,
      sessionId: cartSessionId,
      recommendationType: 'individual'
    };
  }

  // Try to get from line items
  for (const item of lineItems) {
    if (item.properties) {
      const lineTrackingId = item.properties.find((prop: any) => 
        prop.name === '_betterbundle_line_tracking_id'
      )?.value;

      const lineSessionId = item.properties.find((prop: any) => 
        prop.name === '_betterbundle_line_session_id'
      )?.value;

      if (lineTrackingId && lineSessionId) {
        return {
          trackingId: lineTrackingId,
          sessionId: lineSessionId,
          recommendationType: 'individual',
          bundleId: item.properties.find((prop: any) => 
            prop.name === '_betterbundle_line_bundle_id'
          )?.value
        };
      }
    }
  }

  return null;
}

/**
 * Calculate attributed revenue from line items with tracking
 */
function calculateAttributedRevenue(
  lineItems: any[],
  trackingData: {
    trackingId: string;
    sessionId: string;
    recommendationType: string;
    bundleId?: string;
  }
): number {
  let attributedRevenue = 0;

  for (const item of lineItems) {
    if (item.properties) {
      const hasTracking = item.properties.some((prop: any) => 
        prop.name === '_betterbundle_line_tracking_id' &&
        prop.value === trackingData.trackingId
      );

      if (hasTracking) {
        const itemRevenue = parseFloat(item.price) * item.quantity;
        attributedRevenue += itemRevenue;
      }
    }
  }

  return attributedRevenue;
}

/**
 * Update shop analytics with attributed revenue
 */
async function updateShopAnalytics(
  shopDomain: string,
  attributedRevenue: number,
  orderId: string
): Promise<void> {
  try {
    // Get current analytics
    let analytics = await prisma.shopAnalytics.findUnique({
      where: { shopId: shopDomain }
    });

    if (!analytics) {
      // Create new analytics record
      analytics = await prisma.shopAnalytics.create({
        data: {
          shopId: shopDomain,
          totalRecommendationsDisplayed: 0,
          totalRecommendationsClicked: 0,
          totalRecommendationsAddedToCart: 0,
          totalRecommendationsPurchased: 1, // This order
          totalRevenueAttributed: attributedRevenue,
          totalWidgetInteractions: 0,
          lastUpdated: new Date()
        }
      });
    } else {
      // Update existing analytics
      await prisma.shopAnalytics.update({
        where: { shopId: shopDomain },
        data: {
          totalRecommendationsPurchased: {
            increment: 1
          },
          totalRevenueAttributed: {
            increment: attributedRevenue
          },
          lastUpdated: new Date()
        }
      });
    }

    // Log the analytics update
    console.log(`Updated analytics for shop ${shopDomain}: +$${attributedRevenue} attributed revenue`);

  } catch (error) {
    console.error("Failed to update shop analytics:", error);
  }
}
