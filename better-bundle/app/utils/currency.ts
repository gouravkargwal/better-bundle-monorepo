import currencySymbolMap from "currency-symbol-map";

/**
 * Get currency symbol from currency code
 * @param currencyCode - ISO 4217 currency code (e.g., 'USD', 'EUR', 'GBP')
 * @returns Currency symbol (e.g., '$', '€', '£')
 */
export function getCurrencySymbol(currencyCode: string): string {
  return currencySymbolMap(currencyCode) || currencyCode;
}

/**
 * Format amount with currency symbol
 * @param amount - The amount to format
 * @param currencyCode - ISO 4217 currency code
 * @param options - Formatting options
 * @returns Formatted currency string
 */
export function formatCurrency(
  amount: number,
  currencyCode: string,
  options: {
    showSymbol?: boolean;
    decimals?: number;
    locale?: string;
  } = {},
): string {
  const { showSymbol = true, decimals = 2, locale = "en-US" } = options;

  // Fallback to USD if currency code is empty or invalid
  const validCurrencyCode = currencyCode && currencyCode.trim() ? currencyCode : "USD";

  if (showSymbol) {
    // Use Intl.NumberFormat for proper locale-aware formatting
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: validCurrencyCode,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(amount);
  } else {
    // Just format the number without currency symbol
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(amount);
  }
}

/**
 * Format amount using Shopify's money format pattern
 * @param amount - The amount to format
 * @param moneyFormat - Shopify money format (e.g., "${{amount}}", "{{amount}} €")
 * @param decimals - Number of decimal places
 * @returns Formatted currency string using Shopify's pattern
 */
export function formatShopifyMoney(
  amount: number,
  moneyFormat: string,
  decimals: number = 2,
): string {
  const formattedAmount = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount);

  return moneyFormat.replace("{{amount}}", formattedAmount);
}

/**
 * Parse currency amount from formatted string
 * @param formattedAmount - Formatted currency string
 * @param currencyCode - Currency code for validation
 * @returns Parsed amount as number
 */
export function parseCurrencyAmount(
  formattedAmount: string,
  currencyCode: string,
): number {
  // Remove currency symbols and non-numeric characters except decimal point
  const cleanAmount = formattedAmount
    .replace(/[^\d.-]/g, "")
    .replace(/^-/, "-"); // Preserve negative sign

  const amount = parseFloat(cleanAmount);

  if (isNaN(amount)) {
    throw new Error(`Invalid currency amount: ${formattedAmount}`);
  }

  return amount;
}

/**
 * Get currency information including symbol and formatting details
 * @param currencyCode - ISO 4217 currency code
 * @returns Currency information object
 */
export function getCurrencyInfo(currencyCode: string) {
  const symbol = getCurrencySymbol(currencyCode);

  // Common decimal places for different currencies
  const decimalPlaces: Record<string, number> = {
    JPY: 0, // Japanese Yen
    KRW: 0, // South Korean Won
    VND: 0, // Vietnamese Dong
    IDR: 0, // Indonesian Rupiah
    // Most other currencies use 2 decimal places
  };

  return {
    code: currencyCode,
    symbol,
    decimalPlaces: decimalPlaces[currencyCode] ?? 2,
  };
}

/**
 * Convert amount between currencies (requires exchange rate)
 * @param amount - Amount to convert
 * @param fromCurrency - Source currency code
 * @param toCurrency - Target currency code
 * @param exchangeRate - Exchange rate from source to target
 * @returns Converted amount
 */
export function convertCurrency(
  amount: number,
  fromCurrency: string,
  toCurrency: string,
  exchangeRate: number,
): number {
  if (exchangeRate <= 0) {
    throw new Error("Exchange rate must be positive");
  }

  return amount * exchangeRate;
}

// Common currency codes for reference
export const COMMON_CURRENCIES = {
  USD: "US Dollar",
  EUR: "Euro",
  GBP: "British Pound",
  CAD: "Canadian Dollar",
  AUD: "Australian Dollar",
  JPY: "Japanese Yen",
  CHF: "Swiss Franc",
  CNY: "Chinese Yuan",
  INR: "Indian Rupee",
  BRL: "Brazilian Real",
  MXN: "Mexican Peso",
  KRW: "South Korean Won",
  SGD: "Singapore Dollar",
  HKD: "Hong Kong Dollar",
  NOK: "Norwegian Krone",
  SEK: "Swedish Krona",
  DKK: "Danish Krone",
  PLN: "Polish Zloty",
  CZK: "Czech Koruna",
  HUF: "Hungarian Forint",
  RUB: "Russian Ruble",
  TRY: "Turkish Lira",
  ZAR: "South African Rand",
  ILS: "Israeli Shekel",
  AED: "UAE Dirham",
  SAR: "Saudi Riyal",
  THB: "Thai Baht",
  MYR: "Malaysian Ringgit",
  PHP: "Philippine Peso",
  IDR: "Indonesian Rupiah",
  VND: "Vietnamese Dong",
} as const;

export type CurrencyCode = keyof typeof COMMON_CURRENCIES;
