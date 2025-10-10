// features/overview/components/OverviewPage.tsx
import { Page, Layout, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { OverviewHero } from "./OverviewHero";
import { OverviewMetrics } from "./OverviewMetrics";
import { BillingStatus } from "./BillingStatus";
import { QuickActions } from "./QuickActions";
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
      <TitleBar title="Overview" />
      <BlockStack gap="300">
        <Layout>
          <Layout.Section>
            <BlockStack gap="300">
              <OverviewHero shop={data.shop} />
              <OverviewMetrics overviewData={data.overviewData} />
              {data.billingPlan && (
                <BillingStatus billingPlan={data.billingPlan} />
              )}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  gap: "24px",
                }}
              >
                <QuickActions />
                <HelpSection />
              </div>
            </BlockStack>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
