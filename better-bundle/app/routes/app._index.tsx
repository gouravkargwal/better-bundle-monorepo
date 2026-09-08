import { type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  const isOnboarded = await getShopOnboardingCompleted(session.shop);

  if (isOnboarded) {
    // Steady-state dashboard. /app/overview shows the at-a-glance dashboard
    // (and the analysis-progress modal right after "Start Free").
    return redirect("/app/overview");
  }

  return redirect("/app/onboarding");
};
