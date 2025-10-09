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
    // Get shop record
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" });
    }

    // Get commission records with pagination
    const [commissions, totalCount] = await Promise.all([
      prisma.commission_records.findMany({
        where: {
          shop_id: shop.id,
          deleted_at: null, // Only non-deleted records
        },
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
        where: {
          shop_id: shop.id,
          deleted_at: null,
        },
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
