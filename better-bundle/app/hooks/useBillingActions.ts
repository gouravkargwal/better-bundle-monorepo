import { useState } from "react";
import { useAppBridge } from "@shopify/app-bridge-react";

export function useBillingActions() {
  const [isLoading, setIsLoading] = useState(false);
  const [spendingLimit, setSpendingLimit] = useState("1000");
  const app = useAppBridge();

  const handleSetupBilling = async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/billing/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spendingLimit: parseFloat(spendingLimit) }),
      });

      const result = await response.json();

      if (result.success && result.confirmation_url) {
        window.open(result.confirmation_url, "_top");
      } else {
        // Toast notification would go here
        console.error("Failed to setup billing:", result.error);
      }
    } catch (error) {
      console.error("Error setting up billing:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/billing/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      const result = await response.json();

      if (result.success) {
        console.log("Subscription cancelled successfully");
        window.location.reload();
      } else {
        console.error("Failed to cancel subscription:", result.error);
      }
    } catch (error) {
      console.error("Error cancelling subscription:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatCurrency = (amount: number, currency: string = "USD") => {
    // Currency symbols mapping
    const currencySymbols: Record<string, string> = {
      USD: "$",
      EUR: "€",
      GBP: "£",
      CAD: "C$",
      AUD: "A$",
      JPY: "¥",
      INR: "₹",
      CNY: "¥",
      BRL: "R$",
      MXN: "$",
      KRW: "₩",
      RUB: "₽",
      ZAR: "R",
      SEK: "kr",
      NOK: "kr",
      DKK: "kr",
      CHF: "CHF",
      PLN: "zł",
      CZK: "Kč",
      HUF: "Ft",
      RON: "lei",
      BGN: "лв",
      HRK: "kn",
      TRY: "₺",
      ILS: "₪",
      AED: "د.إ",
      SAR: "ر.س",
      QAR: "ر.ق",
      KWD: "د.ك",
      BHD: "د.ب",
      OMR: "ر.ع.",
      JOD: "د.أ",
      LBP: "ل.ل",
      EGP: "£",
      MAD: "د.م.",
      TND: "د.ت",
      DZD: "د.ج",
      LYD: "ل.د",
      SDG: "ج.س.",
      ETB: "Br",
      KES: "KSh",
      UGX: "USh",
      TZS: "TSh",
      ZMW: "ZK",
      BWP: "P",
      SZL: "L",
      LSL: "L",
      NAD: "N$",
      ZWL: "Z$",
      AOA: "Kz",
      MZN: "MT",
      BIF: "FBu",
      RWF: "RF",
      CDF: "FC",
      XAF: "FCFA",
      XOF: "CFA",
      KMF: "CF",
      DJF: "Fdj",
      ERN: "Nfk",
      SOS: "S",
      SSP: "£",
      TZS: "TSh",
      UAH: "₴",
      BYN: "Br",
      MDL: "L",
      GEL: "₾",
      AMD: "֏",
      AZN: "₼",
      KZT: "₸",
      UZS: "сўм",
      KGS: "сом",
      TJS: "SM",
      TMT: "T",
      AFN: "؋",
      PKR: "₨",
      BDT: "৳",
      LKR: "₨",
      NPR: "₨",
      BTN: "Nu.",
      MVR: ".ރ",
      MMK: "K",
      THB: "฿",
      LAK: "₭",
      KHR: "៛",
      VND: "₫",
      IDR: "Rp",
      MYR: "RM",
      SGD: "S$",
      PHP: "₱",
      BND: "B$",
      FJD: "FJ$",
      PGK: "K",
      SBD: "SI$",
      VUV: "Vt",
      WST: "WS$",
      TOP: "T$",
      NZD: "NZ$",
      XPF: "₣",
      ARS: "$",
      BOB: "Bs",
      CLP: "$",
      COP: "$",
      PYG: "₲",
      PEN: "S/",
      UYU: "$U",
      VES: "Bs.S",
      GYD: "G$",
      SRD: "$",
      TTD: "TT$",
      BBD: "Bds$",
      JMD: "J$",
      XCD: "EC$",
      AWG: "ƒ",
      BZD: "BZ$",
      KYD: "CI$",
      BSD: "B$",
      BMD: "BD$",
      CAD: "C$",
      USD: "$",
    };

    const symbol = currencySymbols[currency] || currency;
    
    // Format number with proper decimal places
    const formattedAmount = amount.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    return `${symbol}${formattedAmount}`;
  };

  return {
    isLoading,
    spendingLimit,
    setSpendingLimit,
    handleSetupBilling,
    handleCancelSubscription,
    formatCurrency,
  };
}
