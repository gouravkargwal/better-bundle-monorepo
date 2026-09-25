import prisma from "../db.server";
import logger from "../utils/logger";

/**
 * Actually deletes data for Shopify's mandatory compliance webhooks.
 *
 * Returning 200 satisfies the reviewer; deleting satisfies the obligation.
 * These run raw SQL against a fixed, ordered list of tables rather than going
 * through Prisma models, for two reasons: most foreign keys here are
 * `onDelete: NoAction`, so the order of deletion is load-bearing and worth
 * having visible in one place; and the list stays correct even when a table
 * exists in the database but has not been pulled into the Prisma schema yet.
 *
 * Table names below are constants in this file, never request input.
 */

/**
 * Child-to-parent. Every entry is deleted before anything it points at, so the
 * NoAction foreign keys never block. Adding a table? Put it above its parent.
 */
const SHOP_TABLES_IN_ORDER: { table: string; sql: string }[] = [
  { table: "commission_records", sql: `DELETE FROM commission_records WHERE shop_id = $1` },
  { table: "purchase_attributions", sql: `DELETE FROM purchase_attributions WHERE shop_id = $1` },
  {
    table: "line_item_data",
    sql: `DELETE FROM line_item_data WHERE order_id IN (SELECT id FROM order_data WHERE shop_id = $1)`,
  },
  { table: "refund_data", sql: `DELETE FROM refund_data WHERE shop_id = $1` },
  { table: "order_data", sql: `DELETE FROM order_data WHERE shop_id = $1` },
  { table: "offer_impressions", sql: `DELETE FROM offer_impressions WHERE shop_id = $1` },
  { table: "user_identity_links", sql: `DELETE FROM user_identity_links WHERE shop_id = $1` },
  { table: "user_sessions", sql: `DELETE FROM user_sessions WHERE shop_id = $1` },
  {
    table: "billing_cycles",
    sql: `DELETE FROM billing_cycles WHERE shop_subscription_id IN (SELECT id FROM shop_subscriptions WHERE shop_id = $1)`,
  },
  { table: "shop_subscriptions", sql: `DELETE FROM shop_subscriptions WHERE shop_id = $1` },
  { table: "suspension_audit_log", sql: `DELETE FROM suspension_audit_log WHERE shop_id = $1` },
  { table: "product_vectors", sql: `DELETE FROM product_vectors WHERE shop_id = $1` },
  { table: "product_edges", sql: `DELETE FROM product_edges WHERE shop_id = $1` },
  { table: "product_enrichments", sql: `DELETE FROM product_enrichments WHERE shop_id = $1` },
  { table: "product_data", sql: `DELETE FROM product_data WHERE shop_id = $1` },
  { table: "collection_data", sql: `DELETE FROM collection_data WHERE shop_id = $1` },
  { table: "customer_data", sql: `DELETE FROM customer_data WHERE shop_id = $1` },
  { table: "raw_orders", sql: `DELETE FROM raw_orders WHERE shop_id = $1` },
  { table: "raw_customers", sql: `DELETE FROM raw_customers WHERE shop_id = $1` },
  { table: "raw_products", sql: `DELETE FROM raw_products WHERE shop_id = $1` },
  { table: "raw_collections", sql: `DELETE FROM raw_collections WHERE shop_id = $1` },
];

/**
 * Erase everything held for one shop. Shopify sends `shop/redact` 48 hours
 * after uninstall, and the obligation is the whole record, not just the
 * session row the uninstall handler clears.
 */
/*
 * ponytail: deletes table by table, each committed on its own, rather than in
 * one transaction. A failure halfway therefore leaves the remaining tables
 * populated and nothing retries — the loud ERROR log in the webhook is the only
 * backstop. Acceptable while shops are few and the log is watched; if this ever
 * needs to be unattended, wrap it in `prisma.$transaction` with a raised
 * timeout, or add a sweep that re-runs erasure for shop rows that are gone but
 * whose children are not.
 */
export async function eraseShopData(shopDomain: string): Promise<{
  erased: Record<string, number>;
  shopFound: boolean;
}> {
  const shopRecord = await prisma.shops.findUnique({
    where: { shop_domain: shopDomain },
    select: { id: true },
  });

  const erased: Record<string, number> = {};

  if (!shopRecord) {
    // Still clear auth sessions: they are keyed by domain, so they survive
    // even when the shop row is already gone.
    erased.sessions = await prisma.$executeRawUnsafe(
      `DELETE FROM sessions WHERE shop = $1`,
      shopDomain,
    );
    return { erased, shopFound: false };
  }

  for (const { table, sql } of SHOP_TABLES_IN_ORDER) {
    erased[table] = await prisma.$executeRawUnsafe(sql, shopRecord.id);
  }

  erased.sessions = await prisma.$executeRawUnsafe(
    `DELETE FROM sessions WHERE shop = $1`,
    shopDomain,
  );
  erased.shops = await prisma.$executeRawUnsafe(
    `DELETE FROM shops WHERE id = $1`,
    shopRecord.id,
  );

  return { erased, shopFound: true };
}

/**
 * Erase one customer's personal data.
 *
 * Orders are anonymized rather than deleted: the sale is a financial record and
 * the aggregate is what the recommender learns from, but nothing personally
 * identifying survives. Raw payloads are deleted outright, because they carry
 * the original customer object and cannot be selectively scrubbed.
 */
export async function eraseCustomerData(
  shopDomain: string,
  customerId: string | null,
  ordersToRedact: string[],
): Promise<{ erased: Record<string, number>; shopFound: boolean }> {
  const shopRecord = await prisma.shops.findUnique({
    where: { shop_domain: shopDomain },
    select: { id: true },
  });

  if (!shopRecord) return { erased: {}, shopFound: false };

  const shopId = shopRecord.id;
  const erased: Record<string, number> = {};

  if (customerId) {
    // Attributions point at user_sessions, so they must let go of the session
    // before it can be deleted below.
    erased.purchase_attributions = await prisma.$executeRawUnsafe(
      `UPDATE purchase_attributions
         SET customer_id = NULL, session_id = NULL
       WHERE shop_id = $1 AND customer_id = $2`,
      shopId,
      customerId,
    );

    erased.offer_impressions = await prisma.$executeRawUnsafe(
      `UPDATE offer_impressions SET session_id = NULL
       WHERE shop_id = $1
         AND session_id IN (
           SELECT id FROM user_sessions WHERE shop_id = $1 AND customer_id = $2
         )`,
      shopId,
      customerId,
    );

    // user_sessions carries ip_address and user_agent, which are personal data
    // in their own right.
    erased.user_sessions = await prisma.$executeRawUnsafe(
      `DELETE FROM user_sessions WHERE shop_id = $1 AND customer_id = $2`,
      shopId,
      customerId,
    );

    erased.user_identity_links = await prisma.$executeRawUnsafe(
      `DELETE FROM user_identity_links WHERE shop_id = $1 AND customer_id = $2`,
      shopId,
      customerId,
    );

    erased.customer_data = await prisma.$executeRawUnsafe(
      `DELETE FROM customer_data WHERE shop_id = $1 AND customer_id = $2`,
      shopId,
      customerId,
    );

    erased.raw_customers = await prisma.$executeRawUnsafe(
      `DELETE FROM raw_customers WHERE shop_id = $1 AND shopify_id = $2`,
      shopId,
      customerId,
    );

    erased.order_data = await prisma.$executeRawUnsafe(
      `UPDATE order_data
          SET customer_id = NULL,
              customer_phone = NULL,
              customer_display_name = NULL,
              customer_default_address = NULL,
              customer_verified_email = NULL,
              shipping_address = NULL,
              billing_address = NULL,
              note = NULL,
              note_attributes = NULL,
              extras = NULL
        WHERE shop_id = $1 AND customer_id = $2`,
      shopId,
      customerId,
    );
  }

  if (ordersToRedact.length > 0) {
    // Shopify names the orders explicitly; they may include guest orders that
    // carry no customer id at all, so this runs regardless of the block above.
    erased.raw_orders = await prisma.$executeRawUnsafe(
      `DELETE FROM raw_orders WHERE shop_id = $1 AND shopify_id = ANY($2::text[])`,
      shopId,
      ordersToRedact,
    );

    erased.order_data_by_id = await prisma.$executeRawUnsafe(
      `UPDATE order_data
          SET customer_id = NULL,
              customer_phone = NULL,
              customer_display_name = NULL,
              customer_default_address = NULL,
              customer_verified_email = NULL,
              shipping_address = NULL,
              billing_address = NULL,
              note = NULL,
              note_attributes = NULL,
              extras = NULL
        WHERE shop_id = $1 AND order_id = ANY($2::text[])`,
      shopId,
      ordersToRedact,
    );
  }

  logger.info(
    { shop: shopDomain, customerId, erased },
    "Customer data erased for GDPR request",
  );

  return { erased, shopFound: true };
}
