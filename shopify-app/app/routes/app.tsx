import type { HeadersFunction, LoaderFunctionArgs } from "@remix-run/node";
import { Link, Outlet, useLoaderData, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";
import { AppProvider } from "@shopify/shopify-app-remix/react";
import { NavMenu } from "@shopify/app-bridge-react";
import polarisStyles from "@shopify/polaris/build/esm/styles.css?url";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const links = () => [{ rel: "stylesheet", href: polarisStyles }];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  console.log("🔍 [APP_MAIN] Starting app main loader");

  try {
    // Authenticate once at the parent level - this is the key fix
    console.log("🔍 [APP_MAIN] Authenticating in main route");
    const { session } = await authenticate.admin(request);

    if (!session?.shop) {
      console.error("❌ [APP_MAIN] No shop in session - authentication failed");
      throw new Error("No shop in session");
    }

    console.log("🔍 [APP_MAIN] Authentication SUCCESS - Session details:", {
      id: session?.id,
      shop: session?.shop,
      hasAccessToken: !!session?.accessToken,
    });

    // Get the shop
    let shop = await prisma.shop.findUnique({
      where: { shopDomain: session.shop },
      select: { id: true },
    });

    // If shop doesn't exist, create it
    if (!shop) {
      console.log(
        `🏪 [APP_MAIN] Creating new shop record for: ${session.shop}`,
      );
      shop = await prisma.shop.create({
        data: {
          shopId: session.shop,
          shopDomain: session.shop,
          accessToken: session.accessToken || "",
          email: null,
          planType: "Free",
          currencyCode: null,
          moneyFormat: null,
        },
        select: { id: true },
      });
    }

    return {
      apiKey: process.env.SHOPIFY_API_KEY || "",
      session: {
        id: session.id,
        shop: session.shop,
        hasAccessToken: !!session.accessToken,
      },
      shopId: shop.id,
    };
  } catch (error) {
    console.error("❌ [APP_MAIN] Authentication failed:", error);
    throw error;
  }
};

export default function App() {
  const { apiKey, session, shopId } = useLoaderData<typeof loader>();

  return (
    <AppProvider isEmbeddedApp apiKey={apiKey}>
      <NavMenu>
        <Link to="/app/welcome" rel="home">
          Welcome
        </Link>
        <Link to="/app/dashboard">Dashboard</Link>
        <Link to="/app/widget">Widget Config</Link>
        <Link to="/app/billing">Billing & Plans</Link>
      </NavMenu>
      <Outlet context={{ session, shopId }} />
    </AppProvider>
  );
}

// Shopify needs Remix to catch some thrown responses, so that their headers are included in the response.
export function ErrorBoundary() {
  return boundary.error(useRouteError());
}

export const headers: HeadersFunction = (headersArgs) => {
  // Ensure Shopify boundary headers are properly applied
  const headers = boundary.headers(headersArgs);

  // Add additional security headers for embedded apps
  headers.set("X-Frame-Options", "ALLOWALL");
  headers.set(
    "Content-Security-Policy",
    "frame-ancestors 'self' https://*.myshopify.com",
  );

  // Ensure cookies are properly handled for embedded apps
  headers.set("Cache-Control", "no-cache, no-store, must-revalidate");

  return headers;
};
