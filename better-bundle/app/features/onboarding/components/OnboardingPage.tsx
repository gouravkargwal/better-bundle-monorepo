// features/onboarding/components/OnboardingPage.tsx
import { useNavigation } from "@remix-run/react";
import { Page, Card, Banner, BlockStack, Text } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { OnboardingHero } from "./OnboardingHero";
import { Benefits } from "./Benefits";
import FeatureCard from "./FeatureCard";
import type {
  OnboardingData,
  OnboardingError,
} from "../services/onboarding.types";

interface OnboardingPageProps {
  data: OnboardingData;
  error?: OnboardingError;
}

export function OnboardingPage({ data, error }: OnboardingPageProps) {
  const navigation = useNavigation();
  const isLoading = navigation.state === "submitting";

  return (
    <Page>
      <TitleBar title="Welcome to BetterBundle!" />

      <BlockStack gap="600">
        <OnboardingHero
          isLoading={isLoading}
          error={error}
          pricingTier={data.pricingTier}
        />

        <FeatureCard pricingTier={data.pricingTier} />
        <Benefits />

        {/* Error Display Section */}
        {error && (
          <Card>
            <div style={{ padding: "24px" }}>
              <Banner tone="critical">
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "12px",
                    padding: "20px",
                    backgroundColor: "#FEF2F2",
                    border: "1px solid #FECACA",
                    borderRadius: "12px",
                    boxShadow:
                      "0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)",
                  }}
                >
                  {/* Error Icon */}
                  <div
                    style={{
                      flexShrink: 0,
                      width: "20px",
                      height: "20px",
                      backgroundColor: "#DC2626",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginTop: "2px",
                    }}
                  >
                    <Text
                      as="span"
                      variant="bodySm"
                      fontWeight="bold"
                      color="white"
                    >
                      !
                    </Text>
                  </div>

                  {/* Error Content */}
                  <div style={{ flex: 1 }}>
                    <Text
                      as="h3"
                      variant="headingSm"
                      fontWeight="semibold"
                      color="critical"
                    >
                      Setup Error
                    </Text>
                    <div style={{ marginTop: "4px" }}>
                      <Text as="p" variant="bodyMd" color="critical">
                        {error.error}
                      </Text>
                    </div>
                    <div style={{ marginTop: "12px" }}>
                      <Text as="p" variant="bodySm" color="subdued">
                        Please try again or contact support if the issue
                        persists.
                      </Text>
                    </div>
                  </div>
                </div>
              </Banner>
            </div>
          </Card>
        )}
      </BlockStack>
    </Page>
  );
}
