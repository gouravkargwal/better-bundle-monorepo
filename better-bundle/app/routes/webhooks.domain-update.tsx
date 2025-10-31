import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { admin, session } = await authenticate.webhook(request);

  if (!admin || !session) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    // Fetch current shop details from Shopify API to get the latest domain info
    const shopResponse = await admin.graphql(`
      query {
        shop {
          id
          myshopifyDomain
          primaryDomain {
            host
            url
          }
        }
      }
    `);

    const shopData = await shopResponse.json();
    const shop = shopData.data?.shop;

    if (!shop) {
      throw new Error("Failed to fetch shop data from Shopify API");
    }

    // Extract custom domain (primary domain if different from myshopify domain)
    const customDomain =
      shop.primaryDomain?.host !== shop.myshopifyDomain
        ? shop.primaryDomain?.host
        : null;

    // Update the shop record with the new custom domain
    await prisma.shops.update({
      where: { shop_domain: session.shop },
      data: {
        custom_domain: customDomain,
        updated_at: new Date(),
      },
    });

    return json({
      success: true,
      shopDomain: session.shop,
      customDomain: customDomain,
    });
  } catch (error) {
    console.error("❌ Error processing domain update webhook:", error);
    return json(
      {
        success: false,
        error: "Failed to process domain update webhook",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};
