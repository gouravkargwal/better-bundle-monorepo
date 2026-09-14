import { type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  // At this point, only onboarded shops can reach here (parent loader guards it)
  return redirect("/app/overview");
};
