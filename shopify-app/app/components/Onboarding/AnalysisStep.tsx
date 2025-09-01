import React from "react";
import { BlockStack, Text, Button, Banner } from "@shopify/polaris";

interface AnalysisStepProps {
  onSetupWidget: () => void;
}

export default function AnalysisStep({ onSetupWidget }: AnalysisStepProps) {
  return (
    <BlockStack gap="500" align="center">
      <Text as="h2" variant="headingLg">
        🚀 Analysis Started! Let's Setup Your Widget
      </Text>
      <Text as="p" variant="bodyMd" alignment="center">
        Great! Your store analysis is running in the background. While that's
        happening, let's set up your widget to start collecting customer data.
      </Text>

      <Banner title="📊 Analysis in Progress" tone="info">
        <p>
          Your store data is being analyzed. This usually takes 5-10 minutes.
          We'll notify you when complete.
        </p>
      </Banner>

      <Button variant="primary" size="large" onClick={onSetupWidget}>
        🚀 Setup Widget Now
      </Button>

      <Text as="p" variant="bodySm" tone="subdued" alignment="center">
        Widget setup takes 2-3 minutes. Once active, we'll start collecting
        data.
      </Text>
    </BlockStack>
  );
}
