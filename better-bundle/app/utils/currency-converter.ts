import { getCacheService } from "../services/redis.service";
import { default as getCurrencySymbol } from "currency-symbol-map";

const CACHE_DURATION = 60 * 60; // 1 hour in seconds
const EXCHANGE_RATE_CACHE_PREFIX = "exchange_rate";

/**
 * Get exchange rate from USD to target currency
 * @param targetCurrency - Target currency code
 * @returns Exchange rate from USD to target currency
 */
async function getExchangeRate(targetCurrency: string): Promise<number> {
  const cacheService = await getCacheService();
  const cacheKey = `${EXCHANGE_RATE_CACHE_PREFIX}:${targetCurrency.toUpperCase()}`;

  // Check cache first
  const cached = await cacheService.get<{ rate: number; timestamp: number }>(
    cacheKey,
  );
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION * 1000) {
    return cached.rate;
  }

  try {
    // Use ExchangeRate-API.com (free, no API key required, 1500 requests/month)
    const response = await fetch(
      `https://api.exchangerate-api.com/v4/latest/USD`,
    );

    if (!response.ok) {
      throw new Error(`Exchange rate API failed: ${response.status}`);
    }

    const data = await response.json();
    const rate = data.rates[targetCurrency.toUpperCase()];

    if (!rate) {
      console.warn(`Exchange rate not found for ${targetCurrency}, using 1.0`);
      return 1.0;
    }

    // Cache the rate in Redis
    await cacheService.set(
      cacheKey,
      {
        rate,
        timestamp: Date.now(),
      },
      CACHE_DURATION,
    );

    console.log(`✅ Fetched exchange rate for ${targetCurrency}: ${rate}`);
    return rate;
  } catch (error) {
    console.error(
      `Failed to fetch exchange rate for ${targetCurrency}:`,
      error,
    );

    // Fallback to cached rate if available
    if (cached) {
      console.warn(`Using cached exchange rate for ${targetCurrency}`);
      return cached.rate;
    }

    // Final fallback - assume 1:1 for USD, or use a reasonable default
    if (targetCurrency.toUpperCase() === "USD") {
      return 1.0;
    }

    // For other currencies, use a reasonable default based on common rates
    const fallbackRates: { [key: string]: number } = {
      EUR: 0.85,
      GBP: 0.73,
      CAD: 1.35,
      AUD: 1.5,
      JPY: 150.0,
      CHF: 0.88,
      SEK: 10.5,
      NOK: 10.8,
      DKK: 6.8,
      PLN: 4.0,
      CZK: 22.5,
      HUF: 360.0,
      BGN: 1.66,
      RON: 4.6,
      HRK: 6.4,
      RSD: 100.0,
      MKD: 55.0,
      BAM: 1.7,
      ALL: 95.0,
      ISK: 140.0,
      UAH: 37.0,
      RUB: 90.0,
      BYN: 3.2,
      KZT: 450.0,
      GEL: 2.7,
      AMD: 400.0,
      AZN: 1.7,
      KGS: 89.0,
      TJS: 10.9,
      TMT: 3.5,
      UZS: 12000.0,
      MNT: 3400.0,
      KHR: 4100.0,
      LAK: 21000.0,
      VND: 24000.0,
      THB: 35.0,
      MYR: 4.7,
      SGD: 1.35,
      IDR: 15500.0,
      PHP: 56.0,
      INR: 83.0,
      PKR: 280.0,
      BDT: 110.0,
      LKR: 325.0,
      NPR: 133.0,
      BTN: 83.0,
      MVR: 15.4,
      AFN: 70.0,
      IRR: 42000.0,
      IQD: 1310.0,
      JOD: 0.71,
      KWD: 0.31,
      LBP: 150000.0,
      OMR: 0.38,
      QAR: 3.64,
      SAR: 3.75,
      SYP: 13000.0,
      AED: 3.67,
      YER: 250.0,
      ILS: 3.7,
      JMD: 155.0,
      BBD: 2.0,
      BZD: 2.0,
      XCD: 2.7,
      KYD: 0.83,
      TTD: 6.8,
      AWG: 1.8,
      BSD: 1.0,
      BMD: 1.0,
      BND: 1.35,
      FJD: 2.25,
      GYD: 210.0,
      LRD: 190.0,
      SBD: 8.4,
      SRD: 38.0,
      TVD: 1.5,
      VES: 36.0,
      ARS: 1000.0,
      BOB: 6.9,
      BRL: 5.0,
      CLP: 950.0,
      COP: 4100.0,
      CRC: 520.0,
      CUP: 24.0,
      DOP: 56.0,
      GTQ: 7.8,
      HNL: 24.7,
      MXN: 17.0,
      NIO: 36.8,
      PAB: 1.0,
      PEN: 3.7,
      PYG: 7300.0,
      UYU: 40.0,
      VEF: 36.0,
      ZAR: 18.5,
      BWP: 13.6,
      LSL: 18.5,
      NAD: 18.5,
      SZL: 18.5,
      ZMW: 25.0,
      ZWL: 6000.0,
      AOA: 830.0,
      CDF: 2800.0,
      GMD: 67.0,
      GNF: 8600.0,
      KES: 160.0,
      MAD: 10.0,
      MGA: 4500.0,
      MUR: 45.0,
      NGN: 1600.0,
      RWF: 1300.0,
      SLL: 22000.0,
      SOS: 570.0,
      TZS: 2500.0,
      UGX: 3700.0,
      XAF: 600.0,
      XOF: 600.0,
    };

    const fallbackRate = fallbackRates[targetCurrency.toUpperCase()];
    if (fallbackRate) {
      console.warn(
        `Using fallback exchange rate for ${targetCurrency}: ${fallbackRate}`,
      );
      return fallbackRate;
    }

    console.warn(`No exchange rate available for ${targetCurrency}, using 1.0`);
    return 1.0;
  }
}

/**
 * Convert USD amount to shop currency
 * @param usdAmount - Amount in USD
 * @param targetCurrency - Target currency code
 * @returns Converted amount in target currency
 */
export async function convertUsdToCurrency(
  usdAmount: number,
  targetCurrency: string,
): Promise<number> {
  console.log(
    "🔄 convertUsdToCurrency called with:",
    usdAmount,
    targetCurrency,
  );

  if (targetCurrency.toUpperCase() === "USD") {
    console.log("💰 USD currency, returning original amount:", usdAmount);
    return usdAmount;
  }

  const rate = await getExchangeRate(targetCurrency);
  const result = usdAmount * rate;
  console.log("💰 Conversion result:", usdAmount, "*", rate, "=", result);
  return result;
}

/**
 * Convert shop currency amount to USD
 * @param amount - Amount in shop currency
 * @param fromCurrency - Source currency code
 * @returns Converted amount in USD
 */
export async function convertCurrencyToUsd(
  amount: number,
  fromCurrency: string,
): Promise<number> {
  if (fromCurrency.toUpperCase() === "USD") {
    return amount;
  }

  const rate = await getExchangeRate(fromCurrency);
  return amount / rate;
}

/**
 * Get the trial threshold in shop currency
 * @param shopCurrency - Shop's currency code
 * @param usdThreshold - USD threshold amount to convert
 * @returns Trial threshold in shop currency
 */
export async function getTrialThresholdInShopCurrency(
  shopCurrency: string,
  usdThreshold: number,
): Promise<number> {
  console.log(
    "🔄 getTrialThresholdInShopCurrency called with:",
    shopCurrency,
    usdThreshold,
  );
  const result = await convertUsdToCurrency(usdThreshold, shopCurrency);
  console.log("💰 getTrialThresholdInShopCurrency result:", result);
  return result;
}

/**
 * Format currency amount with proper symbol
 * @param amount - Amount to format
 * @param currencyCode - Currency code
 * @returns Formatted currency string
 */
export function formatCurrencyAmount(
  amount: number,
  currencyCode: string,
): string {
  const symbol = getCurrencySymbol(currencyCode);
  return `${symbol}${amount.toFixed(2)}`;
}

/**
 * Clear the exchange rate cache (useful for testing or manual refresh)
 */
export async function clearExchangeRateCache(): Promise<void> {
  const cacheService = await getCacheService();
  await cacheService.delPattern(`${EXCHANGE_RATE_CACHE_PREFIX}:*`);
}
