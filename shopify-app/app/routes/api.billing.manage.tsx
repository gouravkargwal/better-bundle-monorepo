import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { shopifyBillingService } from "../services/shopify-billing.service";

/**
 * GET - Get billing status and subscription details
 */
export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { admin, session } = await authenticate.admin(request);
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const billingStatus =
      await shopifyBillingService.getBillingStatus(shopDomain);

    return json({
      success: true,
      shop_domain: shopDomain,
      ...billingStatus,
    });
  } catch (error) {
    console.error("Billing management API error:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};

/**
 * POST - Create or manage billing subscription
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { admin, session } = await authenticate.admin(request);
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const formData = await request.formData();
    const action = formData.get("action") as string;

    switch (action) {
      case "create_subscription":
        const subscriptionResult =
          await shopifyBillingService.createBillingSubscription(
            shopDomain,
            session.accessToken,
          );

        if (subscriptionResult.success) {
          return json({
            success: true,
            message: "Billing subscription created successfully",
            subscription_id: subscriptionResult.subscriptionId,
          });
        } else {
          return json(
            {
              success: false,
              error: subscriptionResult.error,
            },
            { status: 400 },
          );
        }

      case "cancel_subscription":
        const cancelResult =
          await shopifyBillingService.cancelSubscription(shopDomain);

        if (cancelResult.success) {
          return json({
            success: true,
            message: "Subscription cancelled successfully",
          });
        } else {
          return json(
            {
              success: false,
              error: cancelResult.error,
            },
            { status: 400 },
          );
        }

      default:
        return json(
          {
            success: false,
            error: "Invalid action",
          },
          { status: 400 },
        );
    }
  } catch (error) {
    console.error("Billing management action error:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};
