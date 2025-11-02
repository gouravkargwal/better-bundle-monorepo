import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { BillingInvoices } from "../features/billing/components/BillingInvoices";
import prisma from "../db.server";

interface UsageRecord {
  id: string;
  createdAt: string;
  description: string;
  price: {
    amount: string;
    currencyCode: string;
  };
}

interface InvoiceItem {
  id: string;
  date: string;
  amount: number;
  status: string;
  description: string;
  type: "usage_record";
  createdAt?: string;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const { session, admin } = await authenticate.admin(request);
  const url = new URL(request.url);

  // Pagination parameters
  const page = parseInt(url.searchParams.get("page") || "1");
  const limit = parseInt(url.searchParams.get("limit") || "10");
  const offset = (page - 1) * limit;

  // Date filter parameters
  const startDate = url.searchParams.get("startDate");
  const endDate = url.searchParams.get("endDate");

  try {
    // Get shop record
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: session.shop },
      select: { id: true, currency_code: true },
    });

    if (!shop) {
      return json({ error: "Shop not found" });
    }

    // Fetch usage records from Shopify
    let usageRecords: InvoiceItem[] = [];
    try {
      // Get all subscriptions to fetch usage records
      const subscriptionsQuery = `
        query GetAppSubscriptions {
          currentAppInstallation {
            allSubscriptions(first: 10) {
              edges {
                node {
                  id
                  name
                  status
                  createdAt
                  lineItems {
                    id
                    plan {
                      pricingDetails {
                        __typename
                        ... on AppRecurringPricing {
                          price {
                            amount
                            currencyCode
                          }
                        }
                        ... on AppUsagePricing {
                          balanceUsed {
                            amount
                            currencyCode
                          }
                          cappedAmount {
                            amount
                            currencyCode
                          }
                        }
                      }
                    }
                    usageRecords(first: 50) {
                      edges {
                        node {
                          id
                          createdAt
                          description
                          price {
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
          }
        }
      `;

      const response = await admin.graphql(subscriptionsQuery);
      const data = await response.json();

      if (data.data?.currentAppInstallation?.allSubscriptions?.edges) {
        const allUsageRecords: UsageRecord[] = [];

        // Collect all usage records from all subscriptions
        for (const subscriptionEdge of data.data.currentAppInstallation
          .allSubscriptions.edges) {
          const subscription = subscriptionEdge.node;

          for (const lineItem of subscription.lineItems || []) {
            if (lineItem.usageRecords?.edges) {
              for (const usageEdge of lineItem.usageRecords.edges) {
                const usageRecord = usageEdge.node;

                // Apply date filter if provided
                if (startDate || endDate) {
                  const recordDate = new Date(usageRecord.createdAt);
                  const recordDateStr = recordDate.toISOString().split("T")[0];

                  if (startDate && recordDateStr < startDate) continue;
                  if (endDate && recordDateStr > endDate) continue;
                }

                allUsageRecords.push(usageRecord);
              }
            }
          }
        }

        // Transform usage records
        usageRecords = allUsageRecords.map((record) => ({
          id: record.id,
          date: new Date(record.createdAt).toISOString().split("T")[0],
          amount: parseFloat(record.price.amount),
          status: "paid", // Usage records are typically paid when created
          description: record.description || "Usage charge",
          type: "usage_record" as const,
          createdAt: record.createdAt,
        }));

        // Sort by date descending
        usageRecords.sort(
          (a, b) =>
            new Date(b.createdAt || b.date).getTime() -
            new Date(a.createdAt || a.date).getTime(),
        );
      }
    } catch (error) {
      console.error("Error fetching usage records:", error);
      // Continue without usage records if there's an error
    }

    // Apply pagination to usage records
    const paginatedItems = usageRecords.slice(offset, offset + limit);
    const totalCount = usageRecords.length;
    const totalPages = Math.ceil(totalCount / limit);

    const invoicesData = {
      invoices: paginatedItems,
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
      filters: {
        startDate: startDate || null,
        endDate: endDate || null,
      },
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
