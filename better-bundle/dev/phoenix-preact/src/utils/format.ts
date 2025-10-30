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
  const validCurrencyCode =
    currencyCode && currencyCode.trim() ? currencyCode : "USD";

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
