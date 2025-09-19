import type { HeadersFunction, LoaderFunctionArgs } from "@remix-run/node";
import { Outlet, useLoaderData, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";

import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { EnhancedNavMenu } from "../components/Navigation/EnhancedNavMenu";
import { getExtensionStatus } from "../services/extension.service";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Ensure shop record exists (fallback if afterAuth didn't run)
  try {
    const existingShop = await prisma.shop.findUnique({
      where: { shopDomain: session.shop },
    });

    if (!existingShop) {
      console.log(
        "🏪 Shop record missing, creating fallback record for:",
        session.shop,
      );
      await prisma.shop.create({
        data: {
          shopDomain: session.shop,
          accessToken: "", // Will be updated by session storage
          isActive: true,
          customDomain: null, // Will be updated when shop data is fetched
        },
      });
    }
  } catch (err) {
    console.error("❌ Fallback shop creation error:", err);
  }

  try {
    const extensionStatus = await getExtensionStatus(session.shop);
    const activeExtensions = Object.values(extensionStatus.extensions).filter(
      (ext) => ext.status === "active",
    ).length;

    return {
      apiKey: process.env.SHOPIFY_API_KEY || "",
      systemStatus: {
        health: extensionStatus.overallStatus,
        extensionsActive: activeExtensions,
        totalExtensions: Object.keys(extensionStatus.extensions).length,
      },
    };
  } catch (error) {
    console.error("Error loading extension status for navigation:", error);
    return {
      apiKey: process.env.SHOPIFY_API_KEY || "",
      systemStatus: {
        health: "critical" as const,
        extensionsActive: 0,
        totalExtensions: 4,
      },
    };
  }
};

export default function App() {
  const { apiKey, systemStatus } = useLoaderData<typeof loader>();

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <EnhancedNavMenu systemStatus={systemStatus} />
      <Outlet />
    </AppProvider>
  );
}

// Shopify needs Remix to catch some thrown responses, so that their headers are included in the response.
export function ErrorBoundary() {
  return boundary.error(useRouteError());
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
