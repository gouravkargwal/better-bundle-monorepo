// app/routes/billing.callback.tsx
// Public callback route for Shopify subscription approval/decline
// Uses HMAC verification instead of session authentication

import { type LoaderFunctionArgs, redirect } from "@remix-run/node";
import crypto from "crypto";
import prisma from "../db.server";
import logger from "../utils/logger";

export async function loader({ request }: LoaderFunctionArgs) {
  try {
    const url = new URL(request.url);
    const hmac = url.searchParams.get("hmac");
    const charge_id = url.searchParams.get("charge_id");
    const shop = url.searchParams.get("shop");

    logger.info(
      { shop, charge_id, hmac: hmac ? "present" : "missing", url: request.url },
      "Billing callback received",
    );

    // Verify HMAC if present (Shopify includes this for security)
    if (hmac) {
      const queryParams = new URLSearchParams(url.search);
      queryParams.delete("hmac");

      const sortedParams = Array.from(queryParams.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, value]) => `${key}=${value}`)
        .join("&");

      const generatedHmac = crypto
        .createHmac("sha256", process.env.SHOPIFY_API_SECRET || "")
        .update(sortedParams)
        .digest("hex");

      if (generatedHmac !== hmac) {
        logger.error(
          { shop, generatedHmac, receivedHmac: hmac },
          "HMAC verification failed",
        );
        return redirect("/app/billing?error=invalid_callback");
      }
    }

    if (!shop) {
      logger.error({ url: request.url }, "No shop parameter in callback");
      return redirect("/app/billing?error=no_shop");
    }

    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      logger.error({ shop }, "Shop not found in billing callback");
      return redirect("/app/billing?error=shop_not_found");
    }

    if (charge_id) {
      // ✅ Subscription was approved by merchant
      logger.info({ shop, charge_id }, "Subscription approved by merchant");

      // Update the Shopify subscription status to ACTIVE
      await prisma.shopify_subscriptions.updateMany({
        where: {
          shop_subscriptions: {
            shop_id: shopRecord.id,
          },
        },
        data: {
          status: "ACTIVE",
          updated_at: new Date(),
        },
      });

      return redirect(`/app/billing?subscription=success&shop=${shop}`);
    } else {
      // ❌ Subscription was declined by merchant
      logger.info({ shop }, "Subscription declined by merchant");

      // Update the Shopify subscription status to DECLINED
      await prisma.shopify_subscriptions.updateMany({
        where: {
          shop_subscriptions: {
            shop_id: shopRecord.id,
          },
        },
        data: {
          status: "DECLINED",
          updated_at: new Date(),
        },
      });

      return redirect(`/app/billing?subscription=cancelled&shop=${shop}`);
    }
  } catch (error) {
    logger.error({ error, url: request.url }, "Billing callback error");
    return redirect("/app/billing?error=callback_failed");
  }
}
