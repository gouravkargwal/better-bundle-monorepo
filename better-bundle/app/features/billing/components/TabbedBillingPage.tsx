import { Page, BlockStack } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import type { BillingState } from "../types/billing.types";
import { BillingPlan } from "./BillingPlan";
import { HeroHeader } from "../../../components/UI/HeroHeader";

interface TabbedBillingPageProps {
  shopId: string;
  shopCurrency: string;
  billingState: BillingState;
  subscriptionStatus?: string | null;
}

export function TabbedBillingPage({
  shopId,
  shopCurrency,
  billingState,
}: TabbedBillingPageProps) {
  return (
    <Page>
      <TitleBar title="Billing" />
      <BlockStack gap="300">
        <HeroHeader
          badge="💳 Billing"
          title="Billing"
          subtitle="Manage your BetterBundle subscription"
          gradient="green"
        />

        <BillingPlan
          shopId={shopId}
          shopCurrency={shopCurrency}
          billingState={billingState}
        />
      </BlockStack>
    </Page>
  );
}
