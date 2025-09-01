import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { useLoaderData } from "@remix-run/react";
import Widget from "../components/Widget/Widget";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  // Get the shop
  let shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    select: { id: true, shopId: true, shopDomain: true },
  });

  // If shop doesn't exist, create it
  if (!shop) {
    console.log(
      `🏪 Creating new shop record for widget config: ${session.shop}`,
    );

    try {
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
        select: { id: true, shopId: true, shopDomain: true },
      });

      console.log(`✅ Shop record created for widget: ${shop.id}`);
    } catch (error) {
      console.error("Failed to create shop record for widget:", error);
      throw new Response("Failed to create shop record", { status: 500 });
    }
  }

  // Get existing widget configuration
  const widgetConfig = await prisma.widgetConfiguration.findUnique({
    where: { shopId: shop.id },
  });

  return {
    shop,
    widgetConfig: widgetConfig || {
      isEnabled: false,
      theme: "auto",
      position: "product_page",
      title: "Frequently Bought Together",
      showImages: true,
      showIndividualButtons: true,
      showBundleTotal: true,
      globalDiscount: 0,
    },
  };
};

export default function WidgetPage() {
  const { shop, widgetConfig } = useLoaderData<typeof loader>();
  return <Widget shop={shop} initialConfig={widgetConfig} />;
}
