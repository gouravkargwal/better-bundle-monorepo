import { type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  const isOnboarded = await getShopOnboardingCompleted(session.shop);

  // ⬅️ DIRECT SERVER REDIRECT - INSTANT!
  if (isOnboarded) {
    return redirect("/app/overview");
  }

  return redirect("/app/onboarding");
};

// ⬅️ NO COMPONENT NEEDED - PURE REDIRECT ROUTE
