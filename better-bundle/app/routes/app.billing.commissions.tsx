import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { CommissionRecords } from "../features/billing/components/CommissionRecords";
import prisma from "../db.server";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const url = new URL(request.url);

  // Pagination parameters
  const page = parseInt(url.searchParams.get("page") || "1");
  const limit = parseInt(url.searchParams.get("limit") || "10");
  const offset = (page - 1) * limit;

  try {
    // Get shop record with subscription info
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: {
        id: true,
        currency_code: true,
        shop_subscriptions: {
          select: {
            status: true,
            is_active: true,
          },
        },
      },
    });

    if (!shop) {
      return json({ error: "Shop not found" });
    }

    // Determine if shop has active paid subscription
    const hasActivePaidSubscription =
      shop.shop_subscriptions?.status === "ACTIVE" &&
      shop.shop_subscriptions?.is_active === true;

    // Build where clause based on subscription status
    const whereClause: any = {
      shop_id: shop.id,
      deleted_at: null, // Only non-deleted records
    };

    // If shop has active paid subscription, exclude trial records
    if (hasActivePaidSubscription) {
      whereClause.billing_phase = {
        not: "TRIAL", // Exclude trial records for paid subscribers
      };
    }

    // Get commission records with pagination
    const [commissions, totalCount] = await Promise.all([
      prisma.commission_records.findMany({
        where: whereClause,
        orderBy: { order_date: "desc" },
        skip: offset,
        take: limit,
        select: {
          id: true,
          order_id: true,
          order_date: true,
          attributed_revenue: true,
          commission_rate: true,
          commission_earned: true,
          status: true,
          billing_phase: true,
        },
      }),
      prisma.commission_records.count({
        where: whereClause,
      }),
    ]);

    const totalPages = Math.ceil(totalCount / limit);

    // Transform data for frontend
    const transformedCommissions = commissions.map((commission) => ({
      id: commission.id,
      orderId: commission.order_id,
      orderDate: commission.order_date.toISOString().split("T")[0],
      attributedRevenue: Number(commission.attributed_revenue),
      commissionRate: Number(commission.commission_rate),
      commissionEarned: Number(commission.commission_earned),
      status: commission.status.toLowerCase(),
      billingPhase: commission.billing_phase.toLowerCase(),
    }));

    const commissionData = {
      commissions: transformedCommissions,
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
      subscriptionStatus: shop.shop_subscriptions?.status || "TRIAL",
      hasActivePaidSubscription,
    };

    return json(commissionData);
  } catch (error) {
    console.error("Billing commissions loader error:", error);
    return json({ error: "Failed to load commission data" });
  }
}

export default function BillingCommissionsPage() {
  const loaderData = useLoaderData<typeof loader>();

  if ("error" in loaderData) {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <p>Error: {loaderData.error}</p>
      </div>
    );
  }

  return (
    <CommissionRecords
      shopId={loaderData.shopId}
      shopCurrency={loaderData.shopCurrency}
      data={loaderData}
    />
  );
}
