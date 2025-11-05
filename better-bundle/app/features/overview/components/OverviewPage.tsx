// features/overview/components/OverviewPage.tsx
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { OverviewHero } from "./OverviewHero";
import { OverviewMetrics } from "./OverviewMetrics";
import { ValueCommunicationBanner } from "./ValueCommunicationBanner";
import { ROIValueProofSection } from "./ROIValueProofSection";
import { BillingStatus } from "./BillingStatus";
import { HelpSection } from "./HelpSection";
import type { OverviewData, OverviewError } from "../services/overview.types";

interface OverviewPageProps {
  data: OverviewData;
  error?: OverviewError;
}

export function OverviewPage({ data, error }: OverviewPageProps) {
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

              {/* Value Communication Banner */}
              <ValueCommunicationBanner
                subscriptionStatus={
                  data.overviewData.activePlan?.status || "ACTIVE"
                }
                totalRevenueGenerated={data.overviewData.totalRevenue}
                currency={data.overviewData.currency}
                commissionRate={
                  data.overviewData.activePlan?.commissionRate || 0.03
                }
                commissionCharged={data.overviewData.commissionCharged}
                isTrialPhase={data.overviewData.isTrialPhase}
              />

              {/* Key Performance Metrics */}
              <OverviewMetrics overviewData={data.overviewData} />

              {/* ROI & Value Proof Section */}
              <ROIValueProofSection
                totalRevenueGenerated={data.overviewData.totalRevenue}
                currency={data.overviewData.currency}
                commissionRate={
                  data.overviewData.activePlan?.commissionRate || 0.03
                }
                isTrialPhase={data.overviewData.isTrialPhase}
                commissionCharged={data.overviewData.commissionCharged}
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
                  commissionRate={
                    data.overviewData.activePlan?.commissionRate || 0.03
                  }
                  isTrialPhase={data.overviewData.isTrialPhase}
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
