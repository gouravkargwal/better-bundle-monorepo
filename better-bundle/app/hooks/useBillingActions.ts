import { useState } from "react";
import { useRevalidator } from "@remix-run/react";
import logger from "app/utils/logger";

export function useBillingActions() {
  const [isLoading, setIsLoading] = useState(false);

  const revalidator = useRevalidator();

  const handleSetupBilling = async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/billing/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

  return {
    isLoading,
    handleSetupBilling,
    handleCancelSubscription,
  };
}
