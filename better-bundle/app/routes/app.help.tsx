import { json, type LoaderFunctionArgs } from "@remix-run/node";
import {
  Page,
  Card,
  BlockStack,
  Text,
  Link as PolarisLink,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { useLoaderData } from "@remix-run/react";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const email = process.env.SUPPORT_EMAIL ?? "support@betterbundle.app";
  const docsUrl =
    process.env.SUPPORT_DOCS_URL ?? "https://docs.betterbundle.app";
  // E.164 without the leading +, e.g. 14155551234
  const whatsapp = process.env.SUPPORT_WHATSAPP_NUMBER ?? "";
  const supportHours = process.env.SUPPORT_HOURS ?? "Mon–Fri, 9am–6pm UTC";
  const responseTime =
    process.env.SUPPORT_RESPONSE_TIME ?? "Usually replies within a few hours";

  return json({ email, docsUrl, whatsapp, supportHours, responseTime });
};

export default function HelpPage() {
  const { email, docsUrl, whatsapp, supportHours, responseTime } =
    useLoaderData<typeof loader>();
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
              <PolarisLink
                url={`mailto:${email}?subject=BetterBundle%20Support`}
              >
                {email}
              </PolarisLink>
            </Text>
            <Text as="p" variant="bodyMd">
              Documentation:{" "}
              <PolarisLink url={docsUrl} external>
                {docsUrl.replace(/^https?:\/\//, "")}
              </PolarisLink>
            </Text>
            {whatsapp ? (
              <Text as="p" variant="bodyMd">
                WhatsApp:{" "}
                <PolarisLink
                  url={`https://wa.me/${whatsapp}?text=Hello%20BetterBundle%20support`}
                  external
                >
                  Message us on WhatsApp
                </PolarisLink>
              </Text>
            ) : null}
            <Text as="p" variant="bodySm">
              {responseTime}
            </Text>
            <Text as="p" variant="bodySm">
              Support hours: {supportHours}
            </Text>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
