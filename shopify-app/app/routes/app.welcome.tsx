import { useNavigate } from "@remix-run/react";
import { Card, Button, BlockStack, Text, Layout, Page } from "@shopify/polaris";
import PricingPlan from "app/components/Billing/PricingPlan";

export default function Welcome() {
  const navigate = useNavigate();

  const handleGetStarted = () => {
    navigate("/app/dashboard");
  };

  return (
    <Page title="Welcome to BetterBundle">
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400" align="center">
              <Text as="h1" variant="displayLg">
                🚀 BetterBundle
              </Text>
              <Text as="p" variant="headingMd" alignment="center">
                Boost your sales with AI-powered product bundle recommendations
              </Text>
              <Text as="p" variant="bodyMd" alignment="center">
                Automatically suggest complementary products to increase cart
                value and customer satisfaction
              </Text>

              <Button onClick={handleGetStarted} variant="primary" size="large">
                🎯 Get Started Now
              </Button>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
      <PricingPlan />
    </Page>
  );
}
