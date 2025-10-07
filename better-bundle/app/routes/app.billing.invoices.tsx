import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export default function InvoicesRoute() {
  return null;
}

export async function loader({ request }: LoaderFunctionArgs) {
  console.log("🟢 INVOICES LOADER CALLED");

  try {
    // authenticate.admin works for fetcher in resource routes
    const { session } = await authenticate.admin(request);
    const { shop } = session;

    console.log("✅ Shop:", shop);

    const shopInfo = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true },
    });

    if (!shopInfo?.id) {
      console.error("❌ Shop not found");
      return json(
        { error: "Shop info not found", recentInvoices: [] },
        { status: 404 },
      );
    }

    const recentInvoices = await prisma.billing_invoices.findMany({
      where: { shop_id: shopInfo.id },
      orderBy: { created_at: "desc" },
      take: 20,
      select: {
        id: true,
        invoice_number: true,
        status: true,
        total: true,
        subtotal: true,
        currency: true,
        period_start: true,
        period_end: true,
        due_date: true,
        paid_at: true,
        created_at: true,
        shopify_charge_id: true,
        billing_metadata: true,
      },
    });

    console.log(`✅ Found ${recentInvoices.length} invoices`);

    return json({ recentInvoices, error: null });
  } catch (error: any) {
    console.error("❌ Error:", error);
    return json({ error: error.message, recentInvoices: [] }, { status: 500 });
  }
}
