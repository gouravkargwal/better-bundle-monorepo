import type { LoaderFunctionArgs } from "@remix-run/node";
import {
  Page,
  Card,
  BlockStack,
  Text,
  Link as PolarisLink,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

export default function HelpPage() {
  return (
    <Page>
      <TitleBar title="Help & Support" />
      <BlockStack gap="400">
        <Card>
          <BlockStack gap="300">
            <Text as="h2" variant="headingMd">
              Need help?
            </Text>
            <Text as="p" variant="bodyMd">
              We’re here to help you get the most out of BetterBundle. Reach out
              and we’ll respond promptly.
            </Text>
            <Text as="p" variant="bodyMd">
              Email:{" "}
              <PolarisLink url="mailto:support@betterbundle.app">
                support@betterbundle.app
              </PolarisLink>
            </Text>
            <Text as="p" variant="bodyMd">
              Documentation:{" "}
              <PolarisLink url="https://docs.betterbundle.app" external>
                docs.betterbundle.app
              </PolarisLink>
            </Text>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
