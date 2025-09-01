import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    await authenticate.admin(request);
    return null;
  } catch (error) {
    // Log the error for debugging
    console.error("Authentication error in auth.$ route:", error);
    
    // Re-throw the error so Shopify can handle it properly
    // This prevents masking authentication failures
    throw error;
  }
};
