import prisma from "../db.server";

export type SuspensionAction = "SUSPENDED" | "REACTIVATED";
export type TriggeredBy = "system" | "webhook" | "admin";

export interface SuspensionAuditEntry {
  shopId: string;
  action: SuspensionAction;
  reason?: string;
  triggeredBy?: TriggeredBy;
  metadata?: Record<string, unknown>;
}

/**
 * Log a suspension or reactivation event to the suspension_audit_log table.
 *
 * Uses raw SQL because the table is not (yet) part of the Prisma schema.
 * The table is managed by the Python worker migration script.
 */
export async function logSuspensionEvent(
  params: SuspensionAuditEntry,
): Promise<void> {
  await prisma.$executeRaw`
    INSERT INTO suspension_audit_log (shop_id, action, reason, triggered_by, metadata_json, created_at)
    VALUES (${params.shopId}, ${params.action}, ${params.reason || null},
            ${params.triggeredBy || "system"},
            ${params.metadata ? JSON.stringify(params.metadata) : null}, NOW())
  `;
}
