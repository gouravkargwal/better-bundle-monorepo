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
  orderIds?: string[]; // Order IDs linked to this usage record
  totalRevenue?: number; // Total revenue from orders
  orderCount?: number; // Number of orders
}

interface InvoicesLoaderData {
  invoices: InvoiceItem[];
  pagination: {
    page: number;
    limit: number;
    totalCount: number;
    totalPages: number;
    hasNext: boolean;
    hasPrevious: boolean;
  };
  shopCurrency: string;
  shopId: string;
  shopDomain: string;
  filters: {
    startDate: string | null;
    endDate: string | null;
  };
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

    // Get shop domain for linking to Shopify admin
    const shopDomain = session.shop;

    // Fetch usage records from Shopify
    let usageRecords: InvoiceItem[] = [];
    try {
      // ✅ Strategy 1: Get usage records from ACTIVE subscriptions
      // Usage records are only available on ACTIVE subscriptions
      // Note: allSubscriptions doesn't accept status argument, so we filter in code
      const subscriptionsQuery = `
        query GetAppSubscriptions {
          currentAppInstallation {
            activeSubscriptions {
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
                usageRecords(first: 250) {
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
            # Fallback: Get all subscriptions (we'll filter ACTIVE in code)
            allSubscriptions(first: 20) {
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
                    usageRecords(first: 250) {
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

      const allUsageRecords: UsageRecord[] = [];

      // ✅ Try activeSubscriptions first (preferred)
      if (data.data?.currentAppInstallation?.activeSubscriptions) {
        console.log(
          `Found ${data.data.currentAppInstallation.activeSubscriptions.length} active subscriptions`,
        );

        for (const subscription of data.data.currentAppInstallation
          .activeSubscriptions) {
          console.log(
            `Processing ACTIVE subscription: ${subscription.id}, status: ${subscription.status}, lineItems count: ${subscription.lineItems?.length || 0}`,
          );

          for (const lineItem of subscription.lineItems || []) {
            console.log(
              `Line item: ${lineItem.id}, usageRecords edges: ${lineItem.usageRecords?.edges?.length || 0}`,
            );

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
      }

      // ✅ Fallback to allSubscriptions with ACTIVE status filter
      if (
        allUsageRecords.length === 0 &&
        data.data?.currentAppInstallation?.allSubscriptions?.edges
      ) {
        console.log(
          `No usage records from activeSubscriptions, trying allSubscriptions with ACTIVE filter...`,
        );

        // Collect all usage records from all ACTIVE subscriptions
        for (const subscriptionEdge of data.data.currentAppInstallation
          .allSubscriptions.edges) {
          const subscription = subscriptionEdge.node;

          // Only process ACTIVE subscriptions
          if (subscription.status !== "ACTIVE") {
            continue;
          }

          console.log(
            `Processing ACTIVE subscription: ${subscription.id}, status: ${subscription.status}, lineItems count: ${subscription.lineItems?.length || 0}`,
          );

          for (const lineItem of subscription.lineItems || []) {
            console.log(
              `Line item: ${lineItem.id}, usageRecords edges: ${lineItem.usageRecords?.edges?.length || 0}`,
            );

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
      }

      // ✅ Strategy 2: If no usage records from subscriptions, try getting them from commission records
      if (allUsageRecords.length === 0) {
        console.log(
          "No usage records from subscriptions, checking commission records with usage_record_id...",
        );

        // Get commission records that have been recorded to Shopify
        const recordedCommissions = await prisma.commission_records.findMany({
          where: {
            shop_id: shop.id,
            shopify_usage_record_id: {
              not: null,
            },
            deleted_at: null,
            billing_phase: "PAID",
            status: "RECORDED",
          },
          select: {
            shopify_usage_record_id: true,
            shopify_response: true,
            commission_charged: true,
            created_at: true,
            order_id: true,
            attributed_revenue: true,
          },
          orderBy: {
            created_at: "desc",
          },
          take: 250, // Limit to most recent 250
        });

        console.log(
          `Found ${recordedCommissions.length} commission records with usage_record_id`,
        );

        // Group by usage_record_id to avoid duplicates
        const usageRecordsMap = new Map<string, InvoiceItem>();

        for (const commission of recordedCommissions) {
          if (!commission.shopify_usage_record_id) continue;

          const usageRecordId = commission.shopify_usage_record_id;
          const shopifyResponse = commission.shopify_response as any;

          // Apply date filter
          if (startDate || endDate) {
            const recordDate = new Date(commission.created_at);
            const recordDateStr = recordDate.toISOString().split("T")[0];

            if (startDate && recordDateStr < startDate) continue;
            if (endDate && recordDateStr > endDate) continue;
          }

          // Get or create usage record entry
          if (!usageRecordsMap.has(usageRecordId)) {
            // Extract data from shopify_response if available
            const price = shopifyResponse?.price || {
              amount: String(commission.commission_charged || 0),
              currencyCode: shop.currency_code || "USD",
            };
            const createdAt =
              shopifyResponse?.created_at || commission.created_at;

            usageRecordsMap.set(usageRecordId, {
              id: usageRecordId,
              date: new Date(createdAt).toISOString().split("T")[0],
              amount: parseFloat(
                price.amount || String(commission.commission_charged || 0),
              ),
              status: "paid",
              description: shopifyResponse?.description || "Usage charge",
              type: "usage_record" as const,
              createdAt: createdAt,
              orderIds: [],
              totalRevenue: 0,
              orderCount: 0,
            });
          }

          // Add order details to existing record
          const record = usageRecordsMap.get(usageRecordId)!;
          if (commission.order_id) {
            if (!record.orderIds) record.orderIds = [];
            if (!record.orderIds.includes(commission.order_id)) {
              record.orderIds.push(commission.order_id);
            }
          }
          record.totalRevenue =
            (record.totalRevenue || 0) +
            Number(commission.attributed_revenue || 0);
          record.orderCount = record.orderIds?.length || 0;
        }

        // Convert map to array
        usageRecords = Array.from(usageRecordsMap.values());

        // Sort by date descending
        usageRecords.sort(
          (a, b) =>
            new Date(b.createdAt || b.date).getTime() -
            new Date(a.createdAt || a.date).getTime(),
        );

        console.log(
          `Created ${usageRecords.length} usage records from commission records`,
        );

        // Apply pagination if we have records from commission data
        if (usageRecords.length > 0) {
          const paginatedItems = usageRecords.slice(offset, offset + limit);
          const totalCount = usageRecords.length;
          const totalPages = Math.ceil(totalCount / limit);

          return json({
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
          });
        }
      }

      // ✅ If we found usage records from subscriptions, process them
      if (allUsageRecords.length > 0) {
        console.log(
          `Found ${allUsageRecords.length} usage records from Shopify subscriptions`,
        );

        // ✅ Show ALL usage records from Shopify, even if commission records aren't linked yet
        // Transform usage record IDs for lookup
        const usageRecordIds = allUsageRecords.map((r) => r.id);

        // Batch fetch all commission records linked to these usage records
        // This is optional enrichment - we'll show usage records even without commission data
        const allCommissionRecords =
          usageRecordIds.length > 0
            ? await prisma.commission_records.findMany({
                where: {
                  shop_id: shop.id,
                  shopify_usage_record_id: {
                    in: usageRecordIds,
                  },
                  deleted_at: null,
                },
                select: {
                  shopify_usage_record_id: true,
                  order_id: true,
                  attributed_revenue: true,
                },
              })
            : [];

        // Group commission records by usage record ID for quick lookup
        const commissionsByUsageRecord = new Map<
          string,
          typeof allCommissionRecords
        >();
        allCommissionRecords.forEach((cr) => {
          if (cr.shopify_usage_record_id) {
            const existing =
              commissionsByUsageRecord.get(cr.shopify_usage_record_id) || [];
            existing.push(cr);
            commissionsByUsageRecord.set(cr.shopify_usage_record_id, existing);
          }
        });

        // ✅ Transform ALL usage records from Shopify (with optional commission linking)
        usageRecords = allUsageRecords.map((record) => {
          // Get linked commission records if available (optional enrichment)
          const commissionRecords =
            commissionsByUsageRecord.get(record.id) || [];

          // Extract order IDs and calculate total revenue from linked commissions
          const orderIds = commissionRecords.map((cr) => cr.order_id);
          const totalRevenue = commissionRecords.reduce(
            (sum, cr) => sum + Number(cr.attributed_revenue),
            0,
          );

          return {
            id: record.id,
            date: new Date(record.createdAt).toISOString().split("T")[0],
            amount: parseFloat(record.price.amount),
            status: "paid", // Usage records are typically paid when created
            description: record.description || "Usage charge",
            type: "usage_record" as const,
            createdAt: record.createdAt,
            orderIds: orderIds.length > 0 ? orderIds : undefined,
            totalRevenue: totalRevenue > 0 ? totalRevenue : undefined,
            orderCount: orderIds.length,
          };
        });

        // Sort by date descending
        usageRecords.sort(
          (a, b) =>
            new Date(b.createdAt || b.date).getTime() -
            new Date(a.createdAt || a.date).getTime(),
        );

        console.log(
          `Final usage records count after processing: ${usageRecords.length}`,
        );
      }
    } catch (error: any) {
      console.error("Error fetching usage records from Shopify:", error);
      // Log more details for debugging
      if (error?.message) {
        console.error("Error message:", error.message);
      }
      if (error?.stack) {
        console.error("Error stack:", error.stack);
      }
      // Continue without usage records if there's an error, but log it
      // This allows the page to load even if Shopify API fails
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
      shopDomain, // Pass shop domain for order links
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
  const loaderData = useLoaderData<typeof loader>() as
    | InvoicesLoaderData
    | { error: string };

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
      shopDomain={loaderData.shopDomain}
      data={loaderData}
    />
  );
}
