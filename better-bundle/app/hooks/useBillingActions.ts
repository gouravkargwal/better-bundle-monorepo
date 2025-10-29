import { useState } from "react";
import { useRevalidator } from "@remix-run/react";
import logger from "app/utils/logger";

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
        body: JSON.stringify({
          spendingLimit: parseFloat(spendingLimit),
          monthlyCap: parseFloat(spendingLimit), // Send monthly cap as well
        }),
      });

      const result = await response.json();

      if (result.success && result.confirmation_url) {
        window.open(result.confirmation_url, "_top");
      } else {
        logger.error({ error: result.error }, "Failed to setup billing");
      }
    } catch (error) {
      logger.error({ error }, "Error setting up billing");
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
        // Revalidate current route data in Remix SPA instead of full reload
        revalidator.revalidate();
      } else {
        logger.error({ error: result.error }, "Failed to cancel subscription");
      }
    } catch (error) {
      logger.error({ error }, "Error cancelling subscription");
    } finally {
      setIsLoading(false);
    }
  };

  const handleIncreaseCap = async (newCap: number) => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/billing/increase-cap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spendingLimit: newCap }),
      });

      const result = await response.json();

      if (result.success) {
        // Revalidate current route data in Remix SPA instead of full reload
        revalidator.revalidate();
        return { success: true, message: result.message };
      } else {
        logger.error({ error: result.error }, "Failed to increase cap");
        return { success: false, error: result.error };
      }
    } catch (error) {
      logger.error({ error }, "Error increasing cap");
      return { success: false, error: "Network error" };
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
    handleIncreaseCap,
  };
}
