import type { HeadersFunction, LoaderFunctionArgs } from "@remix-run/node";
import { Link, Outlet, useLoaderData, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";

import { authenticate } from "../shopify.server";
import prisma from "../db.server";

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

  return { apiKey: process.env.SHOPIFY_API_KEY || "" };
};

export default function App() {
  const { apiKey } = useLoaderData<typeof loader>();

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <NavMenu>
        <Link to="/app" rel="home">
          Home
        </Link>
        <Link to="/app/dashboard">Analytics Dashboard</Link>
        <Link to="/app/widget-config">Widget Configuration</Link>
        <Link to="/app/additional">Additional page</Link>
      </NavMenu>
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
