import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { routeErrorBoundary } from "../components/UI/RouteError";
import { authenticate } from "../shopify.server";
import { BillingCycles } from "../features/billing/components/BillingCycles";
import prisma from "../db.server";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const url = new URL(request.url);

  // Pagination parameters
  const page = parseInt(url.searchParams.get("page") || "1");
  const limit = parseInt(url.searchParams.get("limit") || "10");

  try {
    // Get shop record
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true },
    });

    if (!shop) {
      throw new Response("Shop not found", { status: 404 });
    }

    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shop.id,
        is_active: true,
      },
      select: {
        id: true,
        status: true,
        subscription_type: true,
        started_at: true,
        created_at: true,
      },
    });

    if (!shopSubscription) {
      return json({
        error: "No subscription found",
        cycles: [],
        subscriptionStatus: null,
      });
    }

    // Gracefully fetch live subscription details from Shopify GraphQL
    let activeShopifySub: any = null;
    try {
      const response = await admin.graphql(`
        query GetActiveSubscription {
          currentAppInstallation {
            activeSubscriptions {
              id
              status
              currentPeriodEnd
              lineItems {
                plan {
                  pricingDetails {
                    __typename
                    ... on AppUsagePricing {
                      cappedAmount {
                        amount
                        currencyCode
                      }
                      balanceUsed {
                        amount
                        currencyCode
                      }
                    }
                  }
                }
              }
            }
          }
        }
      `);
      const data = await response.json();
      activeShopifySub =
        data?.data?.currentAppInstallation?.activeSubscriptions?.[0] || null;
    } catch (shopifyErr) {
      console.warn(
        "Could not fetch active subscription from Shopify, degrading gracefully:",
        shopifyErr,
      );
    }

    // Determine current cycle period end
    const now = new Date();
    const periodEnd = activeShopifySub?.currentPeriodEnd
      ? new Date(activeShopifySub.currentPeriodEnd)
      : new Date(now.getTime() + 15 * 24 * 60 * 60 * 1000);

    const subscriptionStart =
      shopSubscription.started_at || shopSubscription.created_at || now;

    // Find earliest commission date to know how far back history goes
    const earliestCommission = await prisma.commission_records.findFirst({
      where: { shop_id: shop.id, deleted_at: null },
      orderBy: { order_date: "asc" },
      select: { order_date: true },
    });

    const oldestDate = earliestCommission?.order_date
      ? new Date(
          Math.min(
            earliestCommission.order_date.getTime(),
            subscriptionStart.getTime(),
          ),
        )
      : subscriptionStart;

    // Build 30-day date windows stepping backward from currentPeriodEnd
    const cycleWindows: Array<{
      cycleNumber: number;
      startDate: Date;
      endDate: Date;
      isCurrent: boolean;
    }> = [];

    let currentWindowEnd = new Date(periodEnd);
    let cycleCounter = 1;

    // Build windows up to the oldest activity or at least 1 cycle
    while (true) {
      const currentWindowStart = new Date(
        currentWindowEnd.getTime() - 30 * 24 * 60 * 60 * 1000,
      );
      cycleWindows.push({
        cycleNumber: cycleCounter,
        startDate: currentWindowStart,
        endDate: currentWindowEnd,
        isCurrent: cycleCounter === 1,
      });

      if (currentWindowStart <= oldestDate || cycleWindows.length >= 24) {
        break;
      }

      currentWindowEnd = currentWindowStart;
      cycleCounter++;
    }

    const totalCount = cycleWindows.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / limit));
    const offset = (page - 1) * limit;
    const paginatedWindows = cycleWindows.slice(offset, offset + limit);

    // Fetch commission dates for the entire paginated range in a single query (no N+1)
    const oldestWindowDate =
      paginatedWindows[paginatedWindows.length - 1]?.startDate;
    const newestWindowDate = paginatedWindows[0]?.endDate;

    const commissionsInPage =
      oldestWindowDate && newestWindowDate
        ? await prisma.commission_records.findMany({
            where: {
              shop_id: shop.id,
              order_date: {
                gte: oldestWindowDate,
                lt: newestWindowDate,
              },
              deleted_at: null,
            },
            select: { order_date: true },
          })
        : [];

    const transformedCycles = paginatedWindows.map((window) => {
      const windowStart = window.startDate.getTime();
      const windowEnd = window.endDate.getTime();
      const commissionCount = commissionsInPage.filter((c) => {
        const t = c.order_date.getTime();
        return t >= windowStart && t < windowEnd;
      }).length;

      return {
        id: `cycle-${window.cycleNumber}`,
        cycleNumber: totalCount - window.cycleNumber + 1,
        startDate: window.startDate.toISOString().split("T")[0],
        endDate: window.endDate.toISOString().split("T")[0],
        status: window.isCurrent ? "active" : "completed",
        commissionCount,
      };
    });

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
    if (error instanceof Response) throw error;
    console.error("Billing cycles loader error:", error);
    throw new Error("Failed to load cycles data");
  }
}

export default function BillingCyclesPage() {
  const loaderData = useLoaderData<typeof loader>();

  // No branching on error strings. A failure never reaches this component —
  // it is thrown and rendered by the ErrorBoundary below. What used to be
  // `loaderData.error !== "No subscription found"` compared the *text* of an
  // error to decide whether it was a failure or an empty state, so rewording
  // that message would have turned an empty state into an error page.
  const cyclesData =
    "error" in loaderData
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

export const ErrorBoundary = routeErrorBoundary;
