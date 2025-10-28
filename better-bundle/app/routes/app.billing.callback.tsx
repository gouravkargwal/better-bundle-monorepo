// app/routes/billing.callback.tsx

import { type LoaderFunctionArgs, redirect } from "@remix-run/node";
import prisma from "../db.server";
import logger from "../utils/logger";

export async function loader({ request }: LoaderFunctionArgs) {
  try {
    const url = new URL(request.url);
    const charge_id = url.searchParams.get("charge_id");
    const shop = url.searchParams.get("shop");

    logger.info(
      { shop, charge_id, url: request.url },
      "Billing callback received",
    );

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
      return redirect(`/app/billing?subscription=success&shop=${shop}`);
    } else {
      // ✅ No charge_id = merchant cancelled
      logger.info({ shop }, "Subscription cancelled by merchant");
      return redirect(`/app/billing?subscription=cancelled&shop=${shop}`);
    }
  } catch (error) {
    logger.error({ error }, "Error in billing callback");

    // ✅ Graceful error handling
    return redirect("/app/billing?error=callback_failed");
  }
}

// ✅ No default export needed - this is just a callback handler
