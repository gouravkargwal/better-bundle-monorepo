/**
 * Currency formatting utilities for BetterBundle
 */

export interface CurrencyConfig {
  currencyCode: string;
  moneyFormat?: string;
}

/**
 * Format a number as currency based on store settings
 */
export function formatCurrency(amount: number, config: CurrencyConfig): string {
  const { currencyCode, moneyFormat } = config;

  // Default to USD if no currency code
  const code = currencyCode || "USD";

  // Try to use the store's money format if available
  if (moneyFormat) {
    return moneyFormat.replace("{{amount}}", formatAmount(amount, code));
  }

  // Fallback to standard currency formatting
  return formatAmount(amount, code);
}

/**
 * Format amount with currency symbol
 */
function formatAmount(amount: number, currencyCode: string): string {
  const formatter = new Intl.NumberFormat(getLocaleForCurrency(currencyCode), {
    style: "currency",
    currency: currencyCode,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return formatter.format(amount);
}

/**
 * Get appropriate locale for currency formatting
 */
function getLocaleForCurrency(currencyCode: string): string {
  const localeMap: Record<string, string> = {
    USD: "en-US",
    EUR: "de-DE",
    GBP: "en-GB",
    CAD: "en-CA",
    AUD: "en-AU",
    INR: "en-IN",
    JPY: "ja-JP",
    CNY: "zh-CN",
    KRW: "ko-KR",
    BRL: "pt-BR",
    MXN: "es-MX",
    SGD: "en-SG",
    HKD: "zh-HK",
    NZD: "en-NZ",
    CHF: "de-CH",
    SEK: "sv-SE",
    NOK: "nb-NO",
    DKK: "da-DK",
    PLN: "pl-PL",
    CZK: "cs-CZ",
    HUF: "hu-HU",
    RUB: "ru-RU",
    TRY: "tr-TR",
    ZAR: "en-ZA",
    AED: "ar-AE",
    SAR: "ar-SA",
    ILS: "he-IL",
    THB: "th-TH",
    MYR: "ms-MY",
    PHP: "en-PH",
    IDR: "id-ID",
    VND: "vi-VN",
  };

  return localeMap[currencyCode] || "en-US";
}

/**
 * Get currency symbol for a currency code
 */
export function getCurrencySymbol(currencyCode: string): string {
  const formatter = new Intl.NumberFormat(getLocaleForCurrency(currencyCode), {
    style: "currency",
    currency: currencyCode,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });

  // Extract the currency symbol from a formatted amount
  const parts = formatter.formatToParts(1234.56);
  const currencyPart = parts.find((part) => part.type === "currency");

  return currencyPart?.value || currencyCode;
}
