import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Guards the shop-redaction table list against drift.
 *
 * `eraseShopData` deletes from a hand-maintained list. Add a table carrying
 * `shop_id` and forget to list it, and redaction silently leaves that data
 * behind — no error, no failing request, just an unmet legal obligation that
 * nothing is looking for. This test is the thing that looks.
 *
 * Reads both files as text so it never imports the Prisma client.
 */

const ROOT = join(__dirname, "..", "..", "..");
const SCHEMA = readFileSync(join(ROOT, "prisma", "schema.prisma"), "utf8");
const ERASURE = readFileSync(
  join(ROOT, "app", "services", "dataErasure.server.ts"),
  "utf8",
);

/** Models declaring a `shop_id` field — i.e. rows belonging to one shop. */
function modelsWithShopId(): string[] {
  const models: string[] = [];
  const modelBlock = /model\s+(\w+)\s*\{([\s\S]*?)\n\}/g;
  let match: RegExpExecArray | null;
  while ((match = modelBlock.exec(SCHEMA)) !== null) {
    const [, name, body] = match;
    if (/^\s*shop_id\s+/m.test(body)) models.push(name);
  }
  return models;
}

/** Tables named in SHOP_TABLES_IN_ORDER. */
function listedTables(): string[] {
  const block = ERASURE.split("SHOP_TABLES_IN_ORDER")[1] ?? "";
  const upTo = block.split("];")[0] ?? "";
  return [...upTo.matchAll(/table:\s*"(\w+)"/g)].map((m) => m[1]);
}

/**
 * Tables deliberately handled outside the list. Each needs a reason, so that
 * adding to this set is a decision rather than a shortcut.
 */
const HANDLED_SEPARATELY: Record<string, string> = {
  shops: "deleted last, by id, after everything referencing it",
};

describe("shop data erasure", () => {
  it("covers every table that holds shop-scoped rows", () => {
    const listed = new Set(listedTables());
    const missing = modelsWithShopId().filter(
      (model) => !listed.has(model) && !(model in HANDLED_SEPARATELY),
    );

    expect(
      missing,
      `These tables carry shop_id but shop/redact never deletes from them. ` +
        `Add each to SHOP_TABLES_IN_ORDER (above its parent), or to ` +
        `HANDLED_SEPARATELY with a reason: ${missing.join(", ")}`,
    ).toEqual([]);
  });

  it("deletes children before their parents", () => {
    const listed = listedTables();
    const before = (table: string) => listed.indexOf(table);

    // Each pair is [child, parent]: the child holds the foreign key, so it has
    // to go first or the delete is refused.
    const pairs: [string, string][] = [
      ["commission_records", "purchase_attributions"],
      ["line_item_data", "order_data"],
      ["refund_data", "order_data"],
      ["purchase_attributions", "user_sessions"],
      ["offer_impressions", "user_sessions"],
      ["billing_cycles", "shop_subscriptions"],
    ];

    for (const [child, parent] of pairs) {
      expect(before(child), `${child} must be deleted before ${parent}`)
        .toBeLessThan(before(parent));
      expect(before(child), `${child} is missing from the list`).toBeGreaterThan(-1);
    }
  });

  it("clears auth sessions, which are keyed by domain not shop id", () => {
    expect(ERASURE).toContain("DELETE FROM sessions WHERE shop = $1");
  });

  it("removes the shop row itself", () => {
    expect(ERASURE).toContain("DELETE FROM shops WHERE id = $1");
  });
});
