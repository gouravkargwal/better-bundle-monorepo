import prisma from "../db.server";

export interface TrialConfig {
  currency_code: string;
  threshold_usd: number;
  symbol: string;
  tier: string;
  description: string;
}

export async function getTrialConfig(
  shopDomain: string,
  shopCurrency: string,
): Promise<TrialConfig | null> {
  try {
    console.log(
      "🔍 Getting trial config for shop:",
      shopDomain,
      "currency:",
      shopCurrency,
    );

    // Get trial configuration for shop's currency
    const trialConfig = await prisma.trial_configs.findFirst({
      where: {
        currency_code: shopCurrency,
        is_active: true,
      },
    });

    console.log("📊 Trial config found:", trialConfig);

    if (!trialConfig) {
      console.warn(
        `No trial configuration found for currency: ${shopCurrency}`,
      );
      return null;
    }

    return {
      currency_code: trialConfig.currency_code,
      threshold_usd: Number(trialConfig.trial_threshold_usd),
      symbol: trialConfig.currency_symbol || "",
      tier: trialConfig.market_tier || "",
      description: trialConfig.market_description || "",
    };
  } catch (error) {
    console.error("Error getting trial configuration:", error);
    return null;
  }
}
