// app/routes/app.onboarding.tsx
import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useActionData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";
import { OnboardingService } from "../features/onboarding/services/onboarding.service";
import { OnboardingPage } from "../features/onboarding/components/OnboardingPage";
import logger from "../utils/logger";

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
  const {
    session,
    admin,
    redirect: authRedirect,
  } = await authenticate.admin(request);

  try {
    const onboardingService = new OnboardingService();
    await onboardingService.completeOnboarding(session, admin);
    return authRedirect("/app");
  } catch (error) {
    logger.error(
      { error, shop: session.shop },
      "Failed to complete onboarding",
    );
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

  return <OnboardingPage data={data} error={actionData} />;
}
