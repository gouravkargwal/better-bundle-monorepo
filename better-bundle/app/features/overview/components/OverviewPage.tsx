// features/overview/components/OverviewPage.tsx
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { OverviewHero } from "./OverviewHero";
import { OverviewMetrics } from "./OverviewMetrics";
import { ValueCommunicationBanner } from "./ValueCommunicationBanner";
import { ROIValueProofSection } from "./ROIValueProofSection";
import { BillingStatus } from "./BillingStatus";
import { HelpSection } from "./HelpSection";
import { SetupProgressCard } from "./SetupProgressCard";
import type { OverviewData, OverviewError } from "../services/overview.types";

interface OverviewPageProps {
  data: OverviewData;
  error?: OverviewError;
}

export function OverviewPage({ data, error }: OverviewPageProps) {
  const isTrialPhase = data?.overviewData?.activePlan?.status === "TRIAL";
  const monthlyPrice = data?.overviewData?.activePlan?.monthlyPrice ?? 99;

  if (error) {
    return (
      <Page>
        <TitleBar title="Overview" />
        <Layout>
          <Layout.Section>
            <div style={{ padding: "24px", textAlign: "center" }}>
              <h2>Unable to load data</h2>
              <p>{error.error}</p>
            </div>
          </Layout.Section>
        </Layout>
      </Page>
    );
  }

  return (
    <Page>
      <TitleBar title="Better Bundle Overview" />
      <BlockStack gap="300">
        <Layout>
          <Layout.Section>
            <BlockStack gap="300">
              {/* Hero Section */}
              <OverviewHero
                subscriptionStatus={data.overviewData.activePlan?.status}
                totalRevenueGenerated={data.overviewData.totalRevenue}
                currency={data.overviewData.currency}
              />

              {/* Setup Progress — shows until user visits extension guide */}
              {!data.setupStatus.isSetupComplete && (
                <SetupProgressCard setupStatus={data.setupStatus} />
              )}

              {/* Trial / Value Banner */}
              <ValueCommunicationBanner
                subscriptionStatus={
                  data.overviewData.activePlan?.status || "ACTIVE"
                }
                totalRevenueGenerated={data.overviewData.totalRevenue}
                currency={data.overviewData.currency}
                monthlyPrice={monthlyPrice}
                isTrialPhase={isTrialPhase}
              />

              {/* Key Performance Metrics */}
              <OverviewMetrics
                overviewData={data.overviewData}
                isTrialPhase={isTrialPhase}
              />

              {/* ROI & Value Proof Section */}
              <ROIValueProofSection
                totalRevenueGenerated={data.overviewData.totalRevenue}
                currency={data.overviewData.currency}
                monthlyPrice={monthlyPrice}
                isTrialPhase={isTrialPhase}
              />

              {/* Billing Status and Help Section */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
                  gap: "16px",
                }}
              >
                <BillingStatus
                  subscriptionStatus={data.overviewData.activePlan?.status}
                  monthlyPrice={monthlyPrice}
                  isTrialPhase={isTrialPhase}
                  totalRevenueGenerated={data.overviewData.totalRevenue}
                  currency={data.overviewData.currency}
                />
                <HelpSection />
              </div>
            </BlockStack>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
