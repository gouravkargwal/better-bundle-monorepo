import { json, type LoaderFunctionArgs } from "@remix-run/node";
import {
  Box,
  Page,
  Card,
  BlockStack,
  Text,
  Link as PolarisLink,
  Badge,
  InlineStack,
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
    <Page
      title="Help"
      subtitle="Reach out by email or WhatsApp — we usually reply within a few hours."
    >
      <TitleBar title="Help & Support" />
      <BlockStack gap="300">

        <Card>
          <div style={{ padding: "24px" }}>
            <BlockStack gap="400">
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "16px",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <Text variant="headingMd" as="h3">
                    📬 Get in touch
                  </Text>
                  <div style={{ marginTop: "4px" }}>
                    <Text as="p" tone="subdued">
                      Choose your preferred way to reach us
                    </Text>
                  </div>
                </div>
                <Badge tone="success" size="large">
                  {responseTime}
                </Badge>
              </div>

              {/* Contact methods */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                  gap: "12px",
                }}
              >
                {/* Email */}
                <Box padding="500" background="bg-surface-info" borderRadius="300">
                  <BlockStack gap="200">
                    <InlineStack align="space-between" blockAlign="center">
                      <Text as="h3" variant="bodyLg" fontWeight="semibold">
                        Email support
                      </Text>
                      <Badge tone="info">Recommended</Badge>
                    </InlineStack>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Best for detailed questions or issues you want on record.
                    </Text>
                    <PolarisLink
                      url={`mailto:${email}?subject=BetterBundle%20Support`}
                      removeUnderline
                    >
                      <Text variant="bodyMd" as="span" fontWeight="medium">
                        {email}
                      </Text>
                    </PolarisLink>
                  </BlockStack>
                </Box>

                {/* WhatsApp */}
                <Box padding="500" background="bg-surface-success" borderRadius="300">
                  <BlockStack gap="200">
                    <Text as="h3" variant="bodyLg" fontWeight="semibold">
                      WhatsApp
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      Fastest way to get a quick answer — chat with us directly.
                    </Text>
                    <Text variant="bodyMd" as="span" fontWeight="medium">
                      {phone}
                    </Text>
                    <div>
                      <a
                        href={whatsappLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ textDecoration: "none" }}
                      >
                        <Button variant="primary" size="medium">
                          Send WhatsApp message
                        </Button>
                      </a>
                    </div>
                  </BlockStack>
                </Box>
              </div>

              {/* Support hours */}
              <Box padding="400" background="bg-surface-warning" borderRadius="300">
                <InlineStack
                  gap="300"
                  align="space-between"
                  blockAlign="center"
                  wrap
                >
                  <Text as="p" variant="bodySm" fontWeight="semibold">
                    🕘 Support hours: {supportHours}
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    {responseTime} — no ticket required
                  </Text>
                </InlineStack>
              </Box>
            </BlockStack>
          </div>
        </Card>
      </BlockStack>
    </Page>
  );
}