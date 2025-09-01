import { Page, Layout } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";

import { Dashboard } from "app/components/Dashboard/Dashboard";

export default function DashboardPage() {
  return (
    <Page>
      <TitleBar title="Dashboard" />
      <Layout>
        <Dashboard />
      </Layout>
    </Page>
  );
}
