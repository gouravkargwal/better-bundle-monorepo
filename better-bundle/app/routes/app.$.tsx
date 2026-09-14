import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Card, BlockStack, Text, Button } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { getShopOnboardingCompleted } from "../services/shop.service";
import { checkServiceSuspensionMiddleware } from "../middleware/serviceSuspension";

interface LoaderData {
  shopDomain: string;
  isOnboarded: boolean;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, redirect } = await authenticate.admin(request);
  const shop = session.shop;

  const isOnboarded = await getShopOnboardingCompleted(shop);

  const { shouldRedirect, redirectUrl } =
    await checkServiceSuspensionMiddleware(request, shop);

  if (shouldRedirect && redirectUrl) {
    return redirect(redirectUrl);
  }

  return json<LoaderData>({ shopDomain: shop, isOnboarded });
};

export default function NotFound() {
  const { isOnboarded } = useLoaderData<typeof loader>();
  const homePath = isOnboarded ? "/app/overview" : "/app/onboarding";

  return (
    <Page title="Page not found">
      <TitleBar title="Page not found" />
      <BlockStack gap="400" align="center">
        <Card>
          <BlockStack gap="300" align="center">
            <Text as="p" variant="bodyMd">
              The page you&apos;re looking for doesn&apos;t exist or has been
              moved.
            </Text>
            <Button primary url={homePath}>
              Go to Home
            </Button>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
