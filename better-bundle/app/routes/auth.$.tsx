import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { redirect } = await authenticate.admin(request);

  // Immediately redirect to app UI after authentication
  // Using the redirect function from authenticate.admin ensures proper
  // handling of embedded app parameters (host, shop, etc.)
  return redirect("/app");
};
