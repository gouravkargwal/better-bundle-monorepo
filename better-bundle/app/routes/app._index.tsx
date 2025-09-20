import { type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { Page } from "@shopify/polaris";
import { getShopOnboardingCompleted } from "app/services/shop.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  console.log("🔍 Index route - checking onboarding status");
  const onboardingCompleted = await getShopOnboardingCompleted(session.shop);
  console.log("🔍 Index route - onboarding completed:", onboardingCompleted);

  if (!onboardingCompleted) {
    console.log("🔄 Index route - redirecting to onboarding");
    return redirect("/app/onboarding");
  }

  console.log("✅ Index route - onboarding completed, showing welcome page");
  return null;
};

export default function Index() {
  return <Page>Welcome Page</Page>;
}
