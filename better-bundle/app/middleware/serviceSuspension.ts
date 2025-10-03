import type { LoaderFunctionArgs } from "@remix-run/node";
import { redirect } from "@remix-run/node";
import {
  checkServiceSuspension,
  getSuspensionMessage,
} from "../utils/serviceSuspension";
import prisma from "../db.server";

/**
 * Middleware to check service suspension status
 * Should be used in loader functions of protected routes
 */
export async function checkServiceSuspensionMiddleware(
  request: LoaderFunctionArgs["request"],
  shopDomain: string,
): Promise<{
  shouldRedirect: boolean;
  redirectUrl?: string;
  suspensionStatus?: any;
}> {
  try {
    // Get shop record
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true },
    });

    if (!shop) {
      return { shouldRedirect: false };
    }

    // Check suspension status
    const suspensionStatus = await checkServiceSuspension(shop.id);

    // If services are suspended and billing setup is required, redirect to billing setup
    if (suspensionStatus.isSuspended && suspensionStatus.requiresBillingSetup) {
      const message = getSuspensionMessage(suspensionStatus);

      if (message.actionRequired && message.actionUrl) {
        return {
          shouldRedirect: true,
          redirectUrl: message.actionUrl,
          suspensionStatus,
        };
      }
    }

    return { shouldRedirect: false, suspensionStatus };
  } catch (error) {
    console.error("Error in service suspension middleware:", error);
    return { shouldRedirect: false };
  }
}

/**
 * Hook to use service suspension status in components
 */
export function useServiceSuspensionStatus(suspensionStatus: any) {
  if (!suspensionStatus) {
    return {
      isSuspended: false,
      message: null,
      actionRequired: false,
    };
  }

  const message = getSuspensionMessage(suspensionStatus);

  return {
    isSuspended: suspensionStatus.isSuspended,
    message,
    actionRequired: message.actionRequired,
    actionText: message.actionText,
    actionUrl: message.actionUrl,
  };
}
