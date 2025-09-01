import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { shopifyBillingService } from "../services/shopify-billing.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { admin, session } = await authenticate.admin(request);
    if (!session?.shop) {
      return json({ error: "Shop not found" }, { status: 400 });
    }

    const shopDomain = session.shop;
    const url = new URL(request.url);
    const chargeId = url.searchParams.get("charge_id");

    if (chargeId) {
      // Update subscription status if needed
      // Shopify automatically activates the subscription
      console.log(
        `Billing confirmed for shop ${shopDomain}, charge ID: ${chargeId}`,
      );
    }

    return json({
      success: true,
      shop_domain: shopDomain,
      charge_id: chargeId,
    });
  } catch (error) {
    console.error("Billing confirmation error:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};

export default function BillingConfirmation() {
  const data = useLoaderData<typeof loader>();

  if (data.error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="max-w-md w-full bg-white rounded-lg shadow-md p-6">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
              <svg
                className="h-6 w-6 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h3 className="mt-2 text-sm font-medium text-gray-900">
              Billing Setup Failed
            </h3>
            <p className="mt-1 text-sm text-gray-500">{data.error}</p>
            <div className="mt-6">
              <a
                href="/app"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
              >
                Return to Dashboard
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-lg shadow-md p-6">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
            <svg
              className="h-6 w-6 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h3 className="mt-2 text-sm font-medium text-gray-900">
            Billing Setup Complete!
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            Your performance-based billing subscription has been activated
            successfully.
          </p>
          <div className="mt-6">
            <a
              href="/app"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
            >
              Go to Dashboard
            </a>
          </div>
          <div className="mt-4">
            <p className="text-xs text-gray-400">
              You'll be charged based on your recommendation performance. No
              upfront costs - only pay for results!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
