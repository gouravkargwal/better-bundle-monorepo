import prisma from "../../../db.server";

/**
 * The merchant's money for the open billing cycle, read only from Postgres.
 *
 * Deliberately makes no Shopify API call. `BillingService.getBillingState`
 * needs an authenticated `admin` client because it reconciles against
 * Shopify's own record of the subscription, which is right for the Billing
 * page but wrong for Home: the page a merchant opens every day should not be
 * able to be slowed down or broken by someone else's API.
 *
 * Everything here comes from `commission_records` and `billing_cycles` — the
 * same tables the charge is actually computed from. That matters more than it
 * sounds: Home used to source its headline revenue figure from
 * `offer_impressions` via the impact service, so the number a merchant saw and
 * the number they were billed on came from different places and could disagree.
 * Read the billing tables and they cannot.
 */

/** Fallbacks matching subscription_plans defaults in the worker's schema. */
const DEFAULT_COMMISSION_RATE = 0.03;
const DEFAULT_CAP_AMOUNT = 29;
const DEFAULT_TRIAL_THRESHOLD = 1000;

export interface CycleMetrics {
  /** True while the shop is still inside its free revenue allowance. */
  isTrial: boolean;

  /** Attributed revenue in the open cycle, or trial-to-date while on trial. */
  attributedRevenue: number;
  /** Commission actually charged so far this cycle. Zero during the trial. */
  billedSoFar: number;
  /** Orders that earned a commission row in scope. */
  ordersInfluenced: number;

  commissionRate: number;
  capAmount: number;

  /** Trial progress. Meaningful only when `isTrial`. */
  trialRevenueEarned: number;
  trialThreshold: number;

  cycleEnd: string | null;
  daysLeftInCycle: number | null;

  currency: string;
  /** False when the shop has no subscription yet — render an empty state. */
  hasSubscription: boolean;
}

const EMPTY: CycleMetrics = {
  isTrial: true,
  attributedRevenue: 0,
  billedSoFar: 0,
  ordersInfluenced: 0,
  commissionRate: DEFAULT_COMMISSION_RATE,
  capAmount: DEFAULT_CAP_AMOUNT,
  trialRevenueEarned: 0,
  trialThreshold: DEFAULT_TRIAL_THRESHOLD,
  cycleEnd: null,
  daysLeftInCycle: null,
  currency: "USD",
  hasSubscription: false,
};

/**
 * Attributed revenue accrued during the trial.
 *
 * Sums TRIAL-phase commission rows only — the same basis the worker uses to
 * decide when the trial ends, so the progress bar and the actual cutover can
 * never disagree. Soft-deleted rows are excluded; every query against
 * `commission_records` has to, and forgetting is silent.
 */
export async function getTrialTotals(
  shopId: string,
): Promise<{ revenue: number; orders: number }> {
  const result = await prisma.commission_records.aggregate({
    where: { shop_id: shopId, billing_phase: "TRIAL", deleted_at: null },
    _sum: { attributed_revenue: true },
    _count: { id: true },
  });
  return {
    revenue: Number(result._sum.attributed_revenue ?? 0),
    orders: result._count.id ?? 0,
  };
}

export async function getTrialRevenueEarned(shopId: string): Promise<number> {
  return (await getTrialTotals(shopId)).revenue;
}

/** Usage charged, revenue attributed, and order count in the open cycle. */
export async function getCurrentCycleUsage(shopSubscriptionId: string): Promise<{
  usageAmount: number;
  attributedRevenue: number;
  orders: number;
  cycleEnd: Date | null;
  capAmount: number | null;
}> {
  const cycle = await prisma.billing_cycles.findFirst({
    where: { shop_subscription_id: shopSubscriptionId, status: "ACTIVE" },
    orderBy: { start_date: "desc" },
  });

  const sub = await prisma.shop_subscriptions.findUnique({
    where: { id: shopSubscriptionId },
    select: {
      shop_id: true,
      cap_amount_override: true,
      subscription_plans: { select: { cap_amount: true } },
    },
  });

  const startDate =
    cycle?.start_date ?? new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
  const dateFilter: { gte: Date; lt?: Date } = { gte: startDate };
  if (cycle?.end_date) {
    dateFilter.lt = cycle.end_date;
  }

  const attributed = sub?.shop_id
    ? await prisma.commission_records.aggregate({
        where: {
          shop_id: sub.shop_id,
          billing_phase: "PAID",
          order_date: dateFilter,
          deleted_at: null,
        },
        _sum: { attributed_revenue: true, commission_charged: true },
        _count: { id: true },
      })
    : {
        _sum: { attributed_revenue: 0, commission_charged: 0 },
        _count: { id: 0 },
      };

  return {
    usageAmount: Number(attributed._sum.commission_charged ?? 0),
    attributedRevenue: Number(attributed._sum.attributed_revenue ?? 0),
    orders: attributed._count.id ?? 0,
    cycleEnd: cycle?.end_date ?? null,
    capAmount:
      cycle?.current_cap_amount !== null && cycle?.current_cap_amount !== undefined
        ? Number(cycle.current_cap_amount)
        : Number(
            sub?.cap_amount_override ??
              sub?.subscription_plans?.cap_amount ??
              29,
          ),
  };
}

export async function getCycleMetrics(shopId: string): Promise<CycleMetrics> {
  const subscription = await prisma.shop_subscriptions.findFirst({
    where: { shop_id: shopId, is_active: true },
    include: { subscription_plans: true },
    orderBy: { created_at: "desc" },
  });

  const shop = await prisma.shops.findUnique({
    where: { id: shopId },
    select: { currency_code: true },
  });
  const currency = shop?.currency_code || "USD";

  if (!subscription) {
    return { ...EMPTY, currency };
  }

  // Override, then plan, then hardcoded default — the same precedence
  // BillingService uses, so the two pages quote identical terms.
  const commissionRate = Number(
    subscription.commission_rate_override ??
      subscription.subscription_plans?.commission_rate ??
      DEFAULT_COMMISSION_RATE,
  );
  const planCap = Number(
    subscription.cap_amount_override ??
      subscription.subscription_plans?.cap_amount ??
      DEFAULT_CAP_AMOUNT,
  );
  const trialThreshold = Number(
    subscription.trial_threshold_override ??
      subscription.subscription_plans?.trial_revenue_threshold ??
      DEFAULT_TRIAL_THRESHOLD,
  );

  const [trial, cycle] = await Promise.all([
    getTrialTotals(shopId),
    getCurrentCycleUsage(subscription.id),
  ]);

  const isTrial =
    subscription.subscription_type === "TRIAL" ||
    subscription.status === "TRIAL";

  const daysLeftInCycle = cycle.cycleEnd
    ? Math.max(
        0,
        Math.ceil(
          (cycle.cycleEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24),
        ),
      )
    : null;

  return {
    isTrial,
    // On trial there is no cycle yet, so the meaningful figure is
    // trial-to-date. Showing an empty cycle would read as "nothing happened".
    attributedRevenue: isTrial ? trial.revenue : cycle.attributedRevenue,
    billedSoFar: cycle.usageAmount,
    // Trial commissions carry no billing_cycle_id — there is no cycle until
    // the shop starts paying — so counting cycle rows reports zero influenced
    // orders for every trialling shop, however many they have actually had.
    ordersInfluenced: isTrial ? trial.orders : cycle.orders,
    commissionRate,
    capAmount: cycle.capAmount ?? planCap,
    trialRevenueEarned: trial.revenue,
    trialThreshold,
    cycleEnd: cycle.cycleEnd ? cycle.cycleEnd.toISOString() : null,
    daysLeftInCycle,
    currency,
    hasSubscription: true,
  };
}
