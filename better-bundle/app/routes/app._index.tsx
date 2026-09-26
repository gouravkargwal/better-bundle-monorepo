import { type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";
import { redirect } from "@remix-run/node";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);
  if (!url.hostname.startsWith("app.")) {
    throw redirect("/");
  }

  const { session, redirect: appRedirect } = await authenticate.admin(request);
  // At this point, only onboarded shops can reach here (parent loader guards it)
  return appRedirect("/app/overview");
};
