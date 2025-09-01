/**
 * Tracking API endpoint for receiving analytics events from the bundle widget extension
 */

import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { redisStreamsService } from "../core/redis/redis-streams.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    // Authenticate the request
    const { admin, session } = await authenticate.admin(request);
    
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const body = await request.json();
    
    if (!body.events || !Array.isArray(body.events)) {
      return json({ error: "Invalid events data" }, { status: 400 });
    }

    const { events, shop_domain, session_id } = body;

    // Validate shop domain matches authenticated session
    if (shop_domain !== shopDomain) {
      return json({ error: "Shop domain mismatch" }, { status: 403 });
    }

    // Process each tracking event
    const processedEvents = [];
    
    for (const event of events) {
      try {
        // Store event in database
        const storedEvent = await prisma.trackingEvent.create({
          data: {
            shopId: shopDomain,
            eventType: event.event_type,
            sessionId: event.session_id,
            trackingId: event.tracking_id,
            userId: event.user_id || null,
            timestamp: new Date(event.timestamp),
            metadata: event.metadata,
            rawEvent: event,
          },
        });

        processedEvents.push({
          id: storedEvent.id,
          event_type: event.event_type,
          timestamp: event.timestamp,
        });

        // Publish event to Redis Streams for real-time processing
        await redisStreamsService.publishTrackingEvent({
          shop_id: shopDomain,
          event_type: event.event_type,
          event_id: storedEvent.id,
          session_id: event.session_id,
          tracking_id: event.tracking_id,
          user_id: event.user_id,
          timestamp: event.timestamp,
          metadata: event.metadata,
        });

      } catch (error) {
        console.error("Failed to process tracking event:", error);
        // Continue processing other events
      }
    }

    // Update shop analytics summary
    await updateShopAnalytics(shopDomain, events);

    return json({
      success: true,
      processed_events: processedEvents.length,
      total_events: events.length,
    });

  } catch (error) {
    console.error("Tracking API error:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};

/**
 * Update shop analytics summary with new tracking data
 */
async function updateShopAnalytics(shopDomain: string, events: any[]) {
  try {
    // Get current analytics summary
    let analytics = await prisma.shopAnalytics.findUnique({
      where: { shopId: shopDomain },
    });

    if (!analytics) {
      // Create new analytics record
      analytics = await prisma.shopAnalytics.create({
        data: {
          shopId: shopDomain,
          totalRecommendationsDisplayed: 0,
          totalRecommendationsClicked: 0,
          totalRecommendationsAddedToCart: 0,
          totalRecommendationsPurchased: 0,
          totalRevenueAttributed: 0,
          totalWidgetInteractions: 0,
          lastUpdated: new Date(),
        },
      });
    }

    // Process events and update counters
    const updates: any = {
      lastUpdated: new Date(),
    };

    for (const event of events) {
      switch (event.event_type) {
        case 'recommendation_displayed':
          updates.totalRecommendationsDisplayed = {
            increment: event.metadata.recommendation_count || 1,
          };
          break;

        case 'recommendation_clicked':
          updates.totalRecommendationsClicked = { increment: 1 };
          break;

        case 'recommendation_added_to_cart':
          updates.totalRecommendationsAddedToCart = { increment: 1 };
          break;

        case 'recommendation_purchased':
          updates.totalRecommendationsPurchased = { increment: 1 };
          updates.totalRevenueAttributed = {
            increment: event.metadata.revenue_attributed || 0,
          };
          break;

        case 'widget_interaction':
          updates.totalWidgetInteractions = { increment: 1 };
          break;
      }
    }

    // Update analytics
    await prisma.shopAnalytics.update({
      where: { shopId: shopDomain },
      data: updates,
    });

  } catch (error) {
    console.error("Failed to update shop analytics:", error);
  }
}

/**
 * GET endpoint for retrieving tracking analytics
 */
export const loader = async ({ request }: ActionFunctionArgs) => {
  try {
    const { admin, session } = await authenticate.admin(request);
    
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const url = new URL(request.url);
    const days = parseInt(url.searchParams.get("days") || "30");
    const eventType = url.searchParams.get("event_type");
    const limit = parseInt(url.searchParams.get("limit") || "100");

    // Build query
    const where: any = {
      shopId: shopDomain,
      timestamp: {
        gte: new Date(Date.now() - days * 24 * 60 * 60 * 1000),
      },
    };

    if (eventType) {
      where.eventType = eventType;
    }

    // Get tracking events
    const events = await prisma.trackingEvent.findMany({
      where,
      orderBy: { timestamp: "desc" },
      take: limit,
      select: {
        id: true,
        eventType: true,
        sessionId: true,
        trackingId: true,
        userId: true,
        timestamp: true,
        metadata: true,
      },
    });

    // Get analytics summary
    const analytics = await prisma.shopAnalytics.findUnique({
      where: { shopId: shopDomain },
    });

    // Get event type breakdown
    const eventTypeBreakdown = await prisma.trackingEvent.groupBy({
      by: ["eventType"],
      where: {
        shopId: shopDomain,
        timestamp: {
          gte: new Date(Date.now() - days * 24 * 60 * 60 * 1000),
        },
      },
      _count: {
        eventType: true,
      },
    });

    // Get daily event counts
    const dailyEvents = await prisma.$queryRaw`
      SELECT 
        DATE(timestamp) as date,
        event_type,
        COUNT(*) as count
      FROM tracking_events 
      WHERE shop_id = ${shopDomain}
        AND timestamp >= DATE_SUB(NOW(), INTERVAL ${days} DAY)
      GROUP BY DATE(timestamp), event_type
      ORDER BY date DESC, event_type
    `;

    return json({
      success: true,
      shop_domain: shopDomain,
      period_days: days,
      events,
      analytics,
      event_type_breakdown: eventTypeBreakdown,
      daily_events: dailyEvents,
      total_events: events.length,
    });

  } catch (error) {
    console.error("Failed to retrieve tracking analytics:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};
