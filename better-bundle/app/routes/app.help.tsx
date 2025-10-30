import { json, type LoaderFunctionArgs } from "@remix-run/node";
import {
  Page,
  Card,
  BlockStack,
  Text,
  Link as PolarisLink,
  Badge,
  InlineStack,
  Box,
  Button,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { useLoaderData } from "@remix-run/react";

const SUPPORT_CONFIG = {
  email: "gouravkargwal@betterbundle.site",
  phone: "+917023074548",
  supportHours: "Mon–Sat, 9am–6pm UTC",
  responseTime: "Usually replies within a few hours",
};

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return json(SUPPORT_CONFIG);
};

export default function HelpPage() {
  const { email, phone, supportHours, responseTime } =
    useLoaderData<typeof loader>();

  const whatsappLink = `https://wa.me/${phone.replace(/\D/g, "")}?text=Hello%20BetterBundle%20support`;

  return (
    <Page>
      <TitleBar title="Help & Support" />
      <BlockStack gap="400">
        {/* Contact Methods Section */}
        <Card>
          <BlockStack gap="300">
            <Box>
              <Text as="h2" variant="headingMd">
                Get in Touch
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                Choose your preferred way to reach us
              </Text>
            </Box>

            {/* Email */}
            <Box
              borderRadius="200"
              borderWidth="1"
              padding="300"
              borderColor="border"
            >
              <InlineStack align="space-between" blockAlign="center">
                <BlockStack gap="100">
                  <Text as="h3" variant="bodyLg" fontWeight="semibold">
                    Email Support
                  </Text>
                  <PolarisLink
                    url={`mailto:${email}?subject=BetterBundle%20Support`}
                    removeUnderline
                  >
                    <Text variant="bodyMd" as="span">
                      {email}
                    </Text>
                  </PolarisLink>
                </BlockStack>
                <Badge tone="info">Recommended</Badge>
              </InlineStack>
            </Box>

            {/* WhatsApp */}
            <Box
              borderRadius="200"
              borderWidth="1"
              padding="300"
              borderColor="border"
            >
              <BlockStack gap="200">
                <Text as="h3" variant="bodyLg" fontWeight="semibold">
                  WhatsApp
                </Text>

                {/* Display Phone Number */}
                <Box>
                  <Text variant="bodyMd" as="span" tone="subdued">
                    {phone}
                  </Text>
                </Box>

                {/* WhatsApp Button/Link */}
                <Box>
                  <a
                    href={whatsappLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: "none" }}
                  >
                    <Button variant="primary" size="medium">
                      Message on WhatsApp
                    </Button>
                  </a>
                </Box>
              </BlockStack>
            </Box>

            {/* Support Info */}
            <Box
              borderRadius="200"
              backgroundColor="bg-surface-secondary"
              padding="300"
            >
              <InlineStack gap="300">
                <BlockStack gap="100" flex="fill">
                  <Text as="p" variant="bodySm" fontWeight="semibold">
                    {responseTime}
                  </Text>
                </BlockStack>
                <BlockStack gap="100" flex="fill">
                  <Text as="p" variant="bodySm">
                    Hours: {supportHours}
                  </Text>
                </BlockStack>
              </InlineStack>
            </Box>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
