import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const { shop } = session;

  try {
    console.log(`🔄 Cancelling pending subscription for shop ${shop}`);

    // Get the current billing plan
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shop,
        status: "active",
      },
      orderBy: { created_at: "desc" },
    });

    if (!billingPlan) {
      return json(
        { success: false, error: "No billing plan found" },
        { status: 404 },
      );
    }

    // If there's a subscription ID, try to cancel it via Shopify API
    if (billingPlan.subscription_id) {
      const cancelMutation = `
        mutation appSubscriptionCancel($id: ID!) {
          appSubscriptionCancel(id: $id) {
            appSubscription {
              id
              status
            }
            userErrors {
              field
              message
            }
          }
        }
      `;

      const cancelResponse = await admin.graphql(cancelMutation, {
        variables: {
          id: billingPlan.subscription_id,
        },
      });

      const cancelData = await cancelResponse.json();
      console.log("Cancel response:", cancelData);

      if (cancelData.data?.appSubscriptionCancel?.userErrors?.length > 0) {
        console.log(
          "Cancel errors:",
          cancelData.data.appSubscriptionCancel.userErrors,
        );
        // Continue with local cancellation even if Shopify API fails
      }
    }

    // Update billing plan status to cancelled
    await prisma.billing_plans.update({
      where: { id: billingPlan.id },
      data: {
        subscription_status: "CANCELLED",
        subscription_cancelled_at: new Date(),
        configuration: {
          ...(billingPlan.configuration as any),
          subscription_status: "CANCELLED",
          subscription_cancelled_at: new Date().toISOString(),
          cancellation_reason: "Cancelled by merchant",
        },
      },
    });

    // Create billing event
    await prisma.billing_events.create({
      data: {
        shop_id: billingPlan.shop_id,
        type: "subscription_cancelled",
        data: {
          subscription_id: billingPlan.subscription_id,
          status: "CANCELLED",
          cancelled_at: new Date().toISOString(),
          reason: "Cancelled by merchant",
        },
        billing_metadata: {
          phase: "subscription_cancellation",
        },
        occurred_at: new Date(),
        processed_at: new Date(),
      },
    });

    console.log(`✅ Successfully cancelled subscription for shop ${shop}`);

    return json({
      success: true,
      message: "Subscription cancelled successfully",
    });
  } catch (error) {
    console.error("Error cancelling subscription:", error);
    return json(
      {
        success: false,
        error: "Failed to cancel subscription",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
