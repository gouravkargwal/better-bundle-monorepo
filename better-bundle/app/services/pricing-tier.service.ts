import prisma from "../db.server";
import { getCurrencySymbol } from "../utils/currency";

export interface PricingTierConfig {
  currency_code: string;
  threshold_amount: number;
  symbol: string;
  tier: string;
  description: string;
  commission_rate: number;
}

export async function getPricingTierConfig(
  shopDomain: string,
  shopCurrency: string,
): Promise<PricingTierConfig | null> {
  try {
    // Get pricing tier configuration for shop's currency
    const pricingTier = await prisma.pricing_tiers.findFirst({
      where: {
        currency: shopCurrency,
        is_active: true,
        is_default: true,
      },
      include: {
        subscription_plans: true,
      },
    });

    if (!pricingTier) {
      console.warn(
        `No pricing tier configuration found for currency: ${shopCurrency}`,
      );
      return null;
    }

    // Parse tier metadata for additional info
    let tierMetadata = {};
    try {
      tierMetadata = pricingTier.tier_metadata
        ? JSON.parse(pricingTier.tier_metadata as string)
        : {};
    } catch (e) {
      console.warn("Failed to parse tier metadata:", e);
    }

    return {
      currency_code: pricingTier.currency,
      threshold_amount: Number(pricingTier.trial_threshold_amount || 200),
      symbol:
        (tierMetadata as any).currency_symbol ||
        getCurrencySymbol(shopCurrency),
      tier: (tierMetadata as any).market_tier || "standard",
      description:
        (tierMetadata as any).description || `${shopCurrency} Market`,
      commission_rate: Number(pricingTier.commission_rate || 0.03),
    };
  } catch (error) {
    console.error("Error getting pricing tier configuration:", error);
    return null;
  }
}
