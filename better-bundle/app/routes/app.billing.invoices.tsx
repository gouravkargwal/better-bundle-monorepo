import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { BillingInvoices } from "../features/billing/components/BillingInvoices";
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

    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shop.id,
        is_active: true,
      },
      select: { id: true },
    });

    if (!shopSubscription) {
      return json({ error: "No active subscription found" });
    }

    // Get billing invoices with pagination
    const [invoices, totalCount] = await Promise.all([
      prisma.billing_invoices.findMany({
        where: {
          shop_subscription_id: shopSubscription.id,
        },
        orderBy: { invoice_date: "desc" },
        skip: offset,
        take: limit,
        select: {
          id: true,
          shopify_invoice_id: true,
          invoice_number: true,
          invoice_date: true,
          total_amount: true,
          status: true,
          description: true,
        },
      }),
      prisma.billing_invoices.count({
        where: {
          shop_subscription_id: shopSubscription.id,
        },
      }),
    ]);

    const totalPages = Math.ceil(totalCount / limit);

    // Transform data for frontend
    const transformedInvoices = invoices.map((invoice) => ({
      id: invoice.invoice_number || invoice.shopify_invoice_id,
      date: invoice.invoice_date.toISOString().split("T")[0],
      amount: Number(invoice.total_amount),
      status: invoice.status.toLowerCase(),
      description:
        invoice.description ||
        `Invoice ${invoice.invoice_number || invoice.shopify_invoice_id}`,
    }));

    const invoicesData = {
      invoices: transformedInvoices,
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

    return json(invoicesData);
  } catch (error) {
    console.error("Billing invoices loader error:", error);
    return json({ error: "Failed to load invoices data" });
  }
}

export default function BillingInvoicesPage() {
  const loaderData = useLoaderData<typeof loader>();

  if ("error" in loaderData) {
    return (
      <div style={{ padding: "24px", textAlign: "center" }}>
        <p>Error: {loaderData.error}</p>
      </div>
    );
  }

  return (
    <BillingInvoices
      shopId={loaderData.shopId}
      shopCurrency={loaderData.shopCurrency}
      data={loaderData}
    />
  );
}
