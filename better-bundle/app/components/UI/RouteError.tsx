import { Banner, BlockStack, Button, Card, Page, Text } from "@shopify/polaris";
import { isRouteErrorResponse, useRouteError } from "@remix-run/react";
import { boundary } from "@shopify/shopify-app-remix/server";

/**
 * The one error page.
 *
 * Replaces a convention where loaders returned `json({ error })` and each route
 * branched on it however it liked — two billing routes rendered a bare
 * `<div><p>Error: …</p></div>` with no Polaris at all, and
 * `app.billing.cycles.tsx` resorted to *string-matching* the error text
 * (`error !== "No subscription found"`) to tell an empty state from a failure.
 *
 * Loaders should now `throw`. "Not found" cases should throw a 404 and be
 * rendered as empty states, not errors — a shop with no subscription yet has
 * not encountered an error.
 */

export function RouteError() {
  return (
    <Page>
      <Card>
        <BlockStack gap="400">
          <Banner tone="critical" title="Something went wrong on this page">
            <Text as="p">
              This is our fault, not yours. Your store data and billing are
              unaffected.
            </Text>
          </Banner>
          <BlockStack gap="200">
            <Button onClick={() => window.location.reload()} variant="primary">
              Reload the page
            </Button>
            <Button url="/app/help" variant="plain">
              Contact support
            </Button>
          </BlockStack>
        </BlockStack>
      </Card>
    </Page>
  );
}

/**
 * Drop-in `ErrorBoundary` for any `app.*` route.
 *
 * The delegation to `boundary.error` on the first line is load-bearing and easy
 * to lose: `authenticate.admin()` throws `Response` objects to drive the
 * 302/401 re-authentication handshake. A boundary that swallows those breaks
 * session recovery, and the merchant sees "something went wrong" instead of
 * being quietly re-authed. Always re-throw a Response before rendering.
 */
export function routeErrorBoundary() {
  const error = useRouteError();

  if (isRouteErrorResponse(error) || error instanceof Response) {
    return boundary.error(error);
  }

  return <RouteError />;
}
