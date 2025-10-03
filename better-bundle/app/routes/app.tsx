import type { HeadersFunction, LoaderFunctionArgs } from "@remix-run/node";
import {
  Outlet,
  useLoaderData,
  useRouteError,
  useLocation,
} from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";

import { authenticate } from "../shopify.server";
import { EnhancedNavMenu } from "../components/Navigation/EnhancedNavMenu";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  return {
    apiKey: process.env.SHOPIFY_API_KEY || "",
    session, // Pass session to child routes
  };
};

export default function App() {
  const { apiKey } = useLoaderData<typeof loader>();
  const location = useLocation();

  // Hide navigation on onboarding page
  const isOnboardingPage = location.pathname === "/app/onboarding";
  const showNavigation = !isOnboardingPage;

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      {showNavigation && <EnhancedNavMenu />}
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
