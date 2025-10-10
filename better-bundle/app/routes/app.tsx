import type { HeadersFunction, LoaderFunctionArgs } from "@remix-run/node";
import {
  Outlet,
  useLoaderData,
  useRouteError,
  useLocation,
  useNavigation,
} from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { Frame } from "@shopify/polaris";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { useState, useEffect } from "react";

import { authenticate } from "../shopify.server";
import { EnhancedNavMenu } from "../components/Navigation/EnhancedNavMenu";
import { getShopOnboardingCompleted } from "../services/shop.service"; // ⬅️ IMPORT

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // ⬅️ ONBOARDING STATUS CHECK KAR
  const isOnboarded = await getShopOnboardingCompleted(session.shop);

  return {
    apiKey: process.env.SHOPIFY_API_KEY || "",
    session,
    isOnboarded, // ⬅️ PASS KAR
  };
};

export default function App() {
  const { apiKey, isOnboarded } = useLoaderData<typeof loader>(); // ⬅️ DESTRUCTURE
  const location = useLocation();
  const navigation = useNavigation();

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const isOnboardingPage = location.pathname === "/app/onboarding";
  const showNavigation = !isOnboardingPage;
  const isNavigating = navigation.state === "loading";

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <Frame>
        {/* ⬅️ PASS ONBOARDING STATUS */}
        {mounted && showNavigation && (
          <EnhancedNavMenu isOnboarded={isOnboarded} />
        )}

        {mounted && isNavigating && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              zIndex: 10000,
              height: "3px",
              background: "#008060",
            }}
          />
        )}

        <div
          style={{
            opacity: mounted && isNavigating ? 0.6 : 1,
            transition: "opacity 150ms ease-in-out",
            minHeight: "100vh",
          }}
        >
          <Outlet />
        </div>
      </Frame>
    </AppProvider>
  );
}

export function ErrorBoundary() {
  return boundary.error(useRouteError());
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
