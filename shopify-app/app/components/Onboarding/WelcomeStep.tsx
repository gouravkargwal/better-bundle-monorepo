import { BlockStack, Text, Button } from "@shopify/polaris";
import PricingPlan from "../Billing/PricingPlan";

interface WelcomeStepProps {
  onStartAnalysis: () => void;
}

export default function WelcomeStep({ onStartAnalysis }: WelcomeStepProps) {
  return (
    <BlockStack gap="500" align="center">
      <Text as="h2" variant="headingLg">
        🎉 Welcome to BetterBundle!
      </Text>
      <Text as="p" variant="bodyMd" alignment="center">
        Boost your sales with AI-powered product bundle recommendations. We
        analyze your customer behavior to suggest products that sell better
        together.
      </Text>

      {/* Use the proper PricingPlan component */}
      <PricingPlan showDetails={true} compact={false} />

      <Button variant="primary" size="large" onClick={onStartAnalysis}>
        🚀 Let's Get Started
      </Button>
      <Text as="p" variant="bodySm" tone="subdued" alignment="center">
        We'll analyze your store data and set up your widget in just a few
        minutes.
      </Text>
    </BlockStack>
  );
}
