// app/routes/app.onboarding.tsx
import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";
import { OnboardingService } from "../features/onboarding/services/onboarding.service";
import { OnboardingPage } from "../features/onboarding/components/OnboardingPage";
import logger from "../utils/logger";

/**
 * Load onboarding data (pricing plan details).
 */
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

  try {
    const onboardingService = new OnboardingService();
    const data = await onboardingService.getOnboardingData(session.shop, admin);
    return json({ ok: true as const, ...data });
  } catch (error) {
    logger.error(
      { err: error, shop: session.shop },
      "Failed to load onboarding data",
    );
    return json(
      {
        ok: false as const,
        error:
          error instanceof Error
            ? error.message
            : "Failed to load onboarding data",
      },
      { status: 500 },
    );
  }
};

/**
 * Action: User clicks "Activate 14-Day Free Trial"
 * → Creates shop + trial subscription + web pixel + starts analysis
 * → Redirects straight to the dashboard
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);

  try {
    const onboardingService = new OnboardingService();
    // completeOnboarding now handles everything: shop setup, trial, web pixel,
    // and starts the data analysis pipeline (Kafka)
    await onboardingService.completeOnboarding(session, admin);

    // Go straight to the analytics dashboard — SSE will stream AI progress
    return redirect("/app/dashboard");
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

/**
 * Single-page onboarding: compact card with app description,
 * data transparency, trial details, and one CTA button.
 */
export default function OnboardingRoute() {
  const loaderData = useLoaderData<typeof loader>();

  const hasLoaderError = loaderData.ok === false;
  const data = hasLoaderError
    ? { subscriptionPlan: null }
    : (loaderData as typeof loaderData & { ok: true });
  const error = hasLoaderError ? loaderData : undefined;

  return <OnboardingPage data={data} error={error} />;
}
