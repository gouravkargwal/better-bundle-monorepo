import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const formData = await request.formData();
    const subscriptionId = formData.get("subscription_id") as string;

    if (!subscriptionId) {
      return json(
        { success: false, error: "Subscription ID is required" },
        { status: 400 },
      );
    }

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get shop subscription with the subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      include: {
        shopify_subscriptions: {
          where: {
            status: "ACTIVE",
          },
        },
      },
    });

    if (!shopSubscription) {
      return json(
        { success: false, error: "Shop subscription not found" },
        { status: 404 },
      );
    }

    // Update shop subscription status
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "ACTIVE",
        activated_at: new Date(),
        updated_at: new Date(),
      },
    });

    // Update Shopify subscription record
    if (shopSubscription.shopify_subscriptions) {
      await prisma.shopify_subscriptions.update({
        where: { id: shopSubscription.shopify_subscriptions.id },
        data: {
          status: "ACTIVE",
          activated_at: new Date(),
          updated_at: new Date(),
        },
      });
    }

    // Reactivate shop services
    await prisma.shops.updateMany({
      where: { shop_domain: shop },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: null,
        updated_at: new Date(),
      },
    });

    // Invalidate suspension cache for all shops with this domain
    const shopRecords = await prisma.shops.findMany({
      where: { shop_domain: shop },
      select: { id: true },
    });

    for (const shopRecord of shopRecords) {
      await invalidateSuspensionCache(shopRecord.id);
    }

    return json({
      success: true,
      message: "Subscription activated successfully",
      subscription_id: subscriptionId,
    });
  } catch (error) {
    logger.error({ error }, "Error activating subscription");
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
