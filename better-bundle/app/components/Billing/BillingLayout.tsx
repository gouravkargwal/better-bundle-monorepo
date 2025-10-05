import { BlockStack, Layout } from "@shopify/polaris";

interface BillingLayoutProps {
  children: React.ReactNode;
}

export function BillingLayout({ children }: BillingLayoutProps) {
  return (
    <BlockStack gap="500">
      <Layout>
        <Layout.Section>{children}</Layout.Section>
      </Layout>
    </BlockStack>
  );
}
