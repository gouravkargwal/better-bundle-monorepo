import { useState } from "react";
import { useRevalidator } from "@remix-run/react";

export function useBillingActions(currency: string = "USD") {
  const [isLoading, setIsLoading] = useState(false);

  // Currency-aware default spending limit
  const defaultLimit = currency === "INR" ? "80000" : "1000";
  const [spendingLimit, setSpendingLimit] = useState(defaultLimit);

  const revalidator = useRevalidator();

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
        // Revalidate current route data in Remix SPA instead of full reload
        revalidator.revalidate();
      } else {
        console.error("Failed to cancel subscription:", result.error);
      }
    } catch (error) {
      console.error("Error cancelling subscription:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return {
    isLoading,
    spendingLimit,
    setSpendingLimit,
    handleSetupBilling,
    handleCancelSubscription,
  };
}
