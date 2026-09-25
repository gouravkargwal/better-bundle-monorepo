import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "app/utils/logger";
import { incrementCounter } from "../services/metrics.service";
import { MAX_CAP, MIN_CAP, isCapInRange } from "../features/billing/capBounds";

/**
 * Lets a merchant set their own spend cap.
 *
 * Shopify will not let an app change a cap on its own: the mutation hands back
 * a `confirmationUrl` and nothing takes effect until the merchant approves it
 * there. So this route only ever returns a URL to send them to — the new cap is
 * written by the `app_subscriptions/update` webhook once Shopify says so.
 */

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    const body = await request.json();
    const requested = Number(body?.cappedAmount);

    if (!Number.isFinite(requested)) {
      return json(
        { success: false, error: "A cap amount is required" },
        { status: 400 },
      );
    }

    const cappedAmount = Math.round(requested * 100) / 100;

    // Rejected rather than clamped: this is an explicit change the merchant
    // asked for, so silently approving a different number would be worse than
    // telling them it is out of range.
    if (!isCapInRange(cappedAmount)) {
      return json(
        {
          success: false,
          error: `Cap must be between ${MIN_CAP} and ${MAX_CAP}`,
        },
        { status: 400 },
      );
    }

    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id, is_active: true },
      select: { id: true, shopify_line_item_id: true },
    });

    if (!shopSubscription?.shopify_line_item_id) {
      // No approved subscription yet, so there is no line item to update. The
      // cap is chosen as part of the initial approval instead.
      return json(
        {
          success: false,
          error: "No active subscription to update. Set up billing first.",
        },
        { status: 400 },
      );
    }

    const currency = shopRecord.currency_code || "USD";

    const mutation = `
      mutation appSubscriptionLineItemUpdate($id: ID!, $cappedAmount: MoneyInput!) {
        appSubscriptionLineItemUpdate(id: $id, cappedAmount: $cappedAmount) {
          confirmationUrl
          userErrors {
            field
            message
          }
        }
      }
    `;

    const response = await admin.graphql(mutation, {
      variables: {
        id: shopSubscription.shopify_line_item_id,
        cappedAmount: { amount: cappedAmount, currencyCode: currency },
      },
    });
    const result = await response.json();

    const errors = result.data?.appSubscriptionLineItemUpdate?.userErrors ?? [];
    if (errors.length > 0) {
      logger.error(
        { errors, shop, cappedAmount },
        "Shopify errors while updating spend cap",
      );
      incrementCounter("billing.cap.shopify_error", { shop });
      return json(
        { success: false, error: errors.map((e: any) => e.message).join(", ") },
        { status: 400 },
      );
    }

    const confirmationUrl =
      result.data?.appSubscriptionLineItemUpdate?.confirmationUrl;

    if (!confirmationUrl) {
      logger.error(
        { shop, cappedAmount },
        "Cap update returned no confirmation URL",
      );
      incrementCounter("billing.cap.error", { shop, reason: "no_url" });
      return json(
        { success: false, error: "Could not start cap update" },
        { status: 500 },
      );
    }

    logger.info({ shop, cappedAmount }, "Spend cap update awaiting approval");
    incrementCounter("billing.cap.requested", { shop });

    return json({
      success: true,
      confirmationUrl,
      cappedAmount,
      message: `Approve your new ${cappedAmount} ${currency} limit in Shopify`,
    });
  } catch (error) {
    logger.error({ error, shop }, "Error updating spend cap");
    incrementCounter("billing.cap.error", { shop, reason: "exception" });
    return json(
      {
        success: false,
        error: "An internal error occurred. Please try again later.",
      },
      { status: 500 },
    );
  }
}
