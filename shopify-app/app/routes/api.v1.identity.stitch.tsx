import { json } from "@remix-run/node";
import type { ActionFunctionArgs } from "@remix-run/node";
import { cors } from "remix-utils/cors";
import { prisma } from "../core/database/prisma.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  if (request.method !== "POST") {
    return json({ success: false, message: "Method not allowed" }, 405);
  }

  try {
    const data = await request.json();
    const { shopDomain, clientId, customerId } = data;

    if (!shopDomain || !clientId || !customerId) {
      return json({ success: false, message: "Missing required fields" }, 400);
    }

    // Find the shop to get the internal shopId
    const shop = await prisma.shop.findUnique({
      where: { shopDomain },
      select: { id: true },
    });

    if (!shop) {
      return json({ success: false, message: "Shop not found" }, 404);
    }

    // Create the identity link
    try {
      await prisma.userIdentityLink.create({
        data: {
          shopId: shop.id,
          clientId,
          customerId,
        },
      });
      console.log(
        `[IDENTITY_STITCH] Successfully linked clientId ${clientId} to customerId ${customerId} for shop ${shop.id}`,
      );
    } catch (error: any) {
      // Gracefully handle unique constraint violations (if the link already exists)
      if (error.code === "P2002") {
        console.log(
          `[IDENTITY_STITCH] Link already exists for clientId ${clientId}, customerId ${customerId}`,
        );
        // Not an error, the desired state is achieved.
        return cors(
          request,
          json({
            success: true,
            message: "Link already exists",
          }),
        );
      }
      // Re-throw other errors
      throw error;
    }

    return cors(request, json({ success: true, message: "Identity linked" }));
  } catch (error) {
    console.error("❌ [IDENTITY_STITCH] API Error:", error);
    return cors(
      request,
      json({ success: false, message: "Internal server error" }, 500),
      { origin: true, credentials: true },
    );
  }
};

// Handle CORS preflight requests
export const options = async ({ request }: ActionFunctionArgs) => {
  return cors(request, json(null, 204), {
    origin: true,
    credentials: true,
    allowedHeaders: ["Content-Type"],
  });
};
