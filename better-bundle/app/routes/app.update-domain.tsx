import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { admin, session } = await authenticate.admin(request);

  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    // Fetch current shop details from Shopify API
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
    const updatedShop = await prisma.shop.update({
      where: { shopDomain: session.shop },
      data: {
        customDomain: customDomain,
        updatedAt: new Date(),
      },
    });

    console.log(
      "✅ Updated custom domain for shop:",
      session.shop,
      "to:",
      customDomain,
    );

    return json({
      success: true,
      shopDomain: session.shop,
      customDomain: customDomain,
      message: customDomain
        ? `Custom domain updated to: ${customDomain}`
        : "No custom domain set (using myshopify domain)",
    });
  } catch (error) {
    console.error("❌ Error updating custom domain:", error);
    return json(
      {
        success: false,
        error: "Failed to update custom domain",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};
