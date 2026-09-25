import { describe, expect, it, vi, beforeEach } from "vitest";

const mockCommissionRows = [
  {
    id: "comm-1",
    order_id: "order-1",
    order_date: "2026-09-20T10:00:00.000Z",
    commission_charged: "15.00",
    attributed_revenue: "500.00",
    status: "PAID",
  },
  {
    id: "comm-2",
    order_id: "order-2",
    order_date: "2026-09-21T11:00:00.000Z",
    commission_charged: "20.00",
    attributed_revenue: "750.00",
    status: "PAID",
  },
  {
    id: "comm-3",
    order_id: "order-3",
    order_date: "2026-09-22T12:00:00.000Z",
    commission_charged: "10.50",
    attributed_revenue: "350.00",
    status: "PENDING",
  },
];

const { mockPrisma, mockAdmin } = vi.hoisted(() => ({
  mockPrisma: {
    shops: { findUnique: vi.fn() },
    $queryRaw: vi.fn(),
  },
  mockAdmin: {
    graphql: vi.fn(),
  },
}));

vi.mock("../../shopify.server", () => ({
  authenticate: {
    admin: vi.fn(),
  },
}));

vi.mock("../../db.server", () => ({ default: mockPrisma }));

import { authenticate } from "../../shopify.server";
import prisma from "../../db.server";
import { loader } from "../app.billing.invoices";

const mockedAuthenticate = vi.mocked(authenticate);
const mockedPrisma = vi.mocked(prisma);

describe("app.billing.invoices - commission records fallback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAuthenticate.admin.mockResolvedValue({
      session: { shop: "test-shop.myshopify.com" },
      admin: mockAdmin,
    } as any);
    mockAdmin.graphql.mockResolvedValue({
      json: async () => ({
        data: {
          currentAppInstallation: {
            activeSubscriptions: [],
            allSubscriptions: { edges: [] },
          },
        },
      }),
    } as any);
  });

  it("returns invoice rows from commission records when Shopify returns zero usageRecords", async () => {
    mockedPrisma.shops.findUnique.mockResolvedValue({
      id: "shop-123",
      currency_code: "USD",
    });
    mockedPrisma.$queryRaw.mockResolvedValueOnce(mockCommissionRows);

    const request = new Request("http://localhost/app/billing/invoices");
    const result = await loader({ request } as any);
    const data = await result.json();

    expect(data.invoices).toHaveLength(3);
    expect(data.invoices[0]).toMatchObject({
      id: "comm-3",
      amount: 10.5,
      status: "pending",
      description: "Commission — order order-3",
      type: "usage_record",
      totalRevenue: 350,
      orderCount: 1,
      orderIds: ["order-3"],
    });
    expect(data.pagination.totalCount).toBe(3);
  });
});
