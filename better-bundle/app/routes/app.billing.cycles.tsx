import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { BillingCycles } from "../features/billing/components/BillingCycles";
import prisma from "../db.server";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);

  // Pagination parameters
  const page = parseInt(url.searchParams.get("page") || "1");
  const limit = parseInt(url.searchParams.get("limit") || "10");
  const offset = (page - 1) * limit;

  try {
    // Get shop record
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" });
    }

    // Get shop subscription (allow TRIAL, TRIAL_COMPLETED, ACTIVE, etc.)
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shop.id,
        is_active: true,
      },
      select: {
        id: true,
        status: true,
        subscription_type: true,
      },
    });

    if (!shopSubscription) {
      return json({
        error: "No subscription found",
        cycles: [],
        subscriptionStatus: null,
      });
    }

    // Get billing cycles with pagination
    const [cycles, totalCount] = await Promise.all([
      prisma.billing_cycles.findMany({
        where: {
          shop_subscription_id: shopSubscription.id,
        },
        orderBy: { cycle_number: "desc" },
        skip: offset,
        take: limit,
        select: {
          id: true,
          cycle_number: true,
          start_date: true,
          end_date: true,
          status: true,
          usage_amount: true,
          current_cap_amount: true,
          commission_count: true,
        },
      }),
      prisma.billing_cycles.count({
        where: {
          shop_subscription_id: shopSubscription.id,
        },
      }),
    ]);

    const totalPages = Math.ceil(totalCount / limit);

    // Transform data for frontend
    const transformedCycles = cycles.map((cycle) => ({
      id: cycle.id,
      cycleNumber: cycle.cycle_number,
      startDate: cycle.start_date.toISOString().split("T")[0],
      endDate: cycle.end_date.toISOString().split("T")[0],
      status: cycle.status.toLowerCase(),
      usageAmount: Number(cycle.usage_amount),
      capAmount: Number(cycle.current_cap_amount),
      commissionCount: cycle.commission_count,
    }));

    const cyclesData = {
      cycles: transformedCycles,
      pagination: {
        page,
        limit,
        totalCount,
        totalPages,
        hasNext: page < totalPages,
        hasPrevious: page > 1,
      },
      shopCurrency: shop.currency_code || "USD",
      shopId: shop.id,
      subscriptionStatus: shopSubscription.status,
      subscriptionType: shopSubscription.subscription_type,
    };

    return json(cyclesData);
  } catch (error) {
    console.error("Billing cycles loader error:", error);
    return json({ error: "Failed to load cycles data" });
  }
}

export default function BillingCyclesPage() {
  const loaderData = useLoaderData<typeof loader>();

  // Handle error case gracefully - show cycles component with empty data
  if ("error" in loaderData && loaderData.error !== "No subscription found") {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <p>Error: {loaderData.error}</p>
      </div>
    );
  }

  // If no subscription found, show empty state (component handles this)
  const cyclesData =
    "error" in loaderData && loaderData.error === "No subscription found"
      ? { cycles: [], pagination: null, shopCurrency: "USD", shopId: "" }
      : loaderData;

  const shopId = "error" in loaderData ? "" : loaderData.shopId;
  const shopCurrency = "error" in loaderData ? "USD" : loaderData.shopCurrency;

  return (
    <BillingCycles
      shopId={shopId}
      shopCurrency={shopCurrency}
      data={cyclesData}
    />
  );
}
