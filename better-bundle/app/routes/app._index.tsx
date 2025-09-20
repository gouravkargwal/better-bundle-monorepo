import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState, useEffect } from "react";
import { authenticate } from "../shopify.server";
import { getDashboardOverview } from "../services/dashboard.service";
import { WelcomePage } from "../components/WelcomePage";
import { ValueFirstOnboarding } from "../components/Onboarding/ValueFirstOnboarding";
import { IndustryTrialCompletion } from "../components/TrialCompletion/IndustryTrialCompletion";
import { Page, Banner, BlockStack, Text } from "@shopify/polaris";
import { getTrialStatus } from "app/utils/trialStatus";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    // Get basic dashboard data for the welcome page
    const dashboardData = await getDashboardOverview(session.shop);

    // Get trial status for industry pattern implementation
    const trialStatus = await getTrialStatus(session.shop);

    // Determine if this is a new installation (within last 24 hours)
    const isNewInstallation =
      !dashboardData ||
      (dashboardData.createdAt &&
        new Date(dashboardData.createdAt) >
          new Date(Date.now() - 24 * 60 * 60 * 1000));

    return {
      dashboardData,
      shop: session.shop,
      isNewUser: !dashboardData || dashboardData.overview.total_revenue === 0,
      isNewInstallation,
      trialStatus,
    };
  } catch (error) {
    console.error("Welcome page loader error:", error);
    return {
      dashboardData: null,
      shop: session.shop,
      isNewUser: true,
      isNewInstallation: true,
      trialStatus: {
        isTrialActive: false,
        currentRevenue: 0,
        threshold: 200,
        remainingRevenue: 200,
        progress: 0,
        needsConsent: false,
      },
      error: "Failed to load dashboard data",
    };
  }
};

export default function Index() {
  const { dashboardData, shop, isNewUser, isNewInstallation, trialStatus } =
    useLoaderData<typeof loader>();

  const [showTrialModal, setShowTrialModal] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState(false);

  useEffect(() => {
    // Show trial completion modal if needed (industry pattern)
    if (trialStatus.needsConsent) {
      setShowTrialModal(true);
    }
  }, [trialStatus.needsConsent]);

  // Industry Pattern 1: Value-First Approach
  // Step 1: Show onboarding for new installations
  if (isNewInstallation && !onboardingCompleted) {
    return (
      <ValueFirstOnboarding
        isNewInstallation={isNewInstallation}
        trialStatus={trialStatus}
        onComplete={() => setOnboardingCompleted(true)}
      />
    );
  }

  // Step 2: Show trial completion modal when trial ends
  if (trialStatus.needsConsent) {
    return (
      <Page>
        <IndustryTrialCompletion
          isOpen={showTrialModal}
          onClose={() => setShowTrialModal(false)}
          trialData={{
            revenue: trialStatus.currentRevenue,
            threshold: trialStatus.threshold,
            currency: "USD",
            period: "trial",
            attributedOrders: Math.floor(trialStatus.currentRevenue / 50), // Estimate
            conversionRate: 15.5, // Example
          }}
          onConsent={() => {
            setShowTrialModal(false);
            // Redirect to billing setup
            window.location.href = "/billing/setup";
          }}
          onContinueFree={() => {
            setShowTrialModal(false);
            // Continue with limited functionality
          }}
        />

        {/* Show main dashboard behind modal */}
        <WelcomePage
          dashboardData={dashboardData}
          shop={shop}
          isNewUser={isNewUser}
        />
      </Page>
    );
  }

  // Step 3: Show main dashboard with trial status
  return (
    <Page>
      {/* Trial status banner */}
      {trialStatus.isTrialActive && (
        <Banner tone="info">
          <BlockStack gap="200">
            <Text as="p">
              <strong>Free Trial Active:</strong> Generate $
              {trialStatus.remainingRevenue.toFixed(2)} more in attributed
              revenue to complete your trial.
            </Text>
            <div style={{ width: "300px" }}>
              <div
                style={{
                  width: "100%",
                  height: "8px",
                  backgroundColor: "#E5E7EB",
                  borderRadius: "4px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${trialStatus.progress}%`,
                    height: "100%",
                    backgroundColor: "#3B82F6",
                    transition: "width 0.3s ease",
                  }}
                />
              </div>
            </div>
          </BlockStack>
        </Banner>
      )}

      {/* Main dashboard */}
      <WelcomePage
        dashboardData={dashboardData}
        shop={shop}
        isNewUser={isNewUser}
      />
    </Page>
  );
}
