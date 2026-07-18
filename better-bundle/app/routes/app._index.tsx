import { type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  const isOnboarded = await getShopOnboardingCompleted(session.shop);

  if (isOnboarded) {
    return redirect("/app/dashboard");
  }

  return redirect("/app/onboarding");
};
