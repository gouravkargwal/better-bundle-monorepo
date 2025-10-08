// app/routes/app.onboarding.tsx
import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useActionData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";
import { OnboardingService } from "../features/onboarding/services/onboarding.service";
import { OnboardingPage } from "../features/onboarding/components/OnboardingPage";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const {
    session,
    redirect: authRedirect,
    admin,
  } = await authenticate.admin(request);
  const onboardingCompleted = await getShopOnboardingCompleted(session.shop);

  if (onboardingCompleted) {
    throw authRedirect("/app");
  }

  const onboardingService = new OnboardingService();
  const data = await onboardingService.getOnboardingData(session.shop, admin);

  return json(data);
};

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🔥 Onboarding action triggered!"); // Debug log

  const {
    session,
    admin,
    redirect: authRedirect,
  } = await authenticate.admin(request);

  try {
    console.log("✅ Starting onboarding completion for:", session.shop);
    const onboardingService = new OnboardingService();
    await onboardingService.completeOnboarding(session, admin);
    console.log("✅ Onboarding completed successfully!");
    return authRedirect("/app");
  } catch (error) {
    console.error("❌ Failed to complete onboarding:", error);
    return json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to complete onboarding. Please try again.",
      },
      { status: 500 },
    );
  }
};

export default function OnboardingRoute() {
  const data = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  console.log(data, actionData, "------------------>");

  return <OnboardingPage data={data} error={actionData} />;
}
