import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { redirect } = await authenticate.admin(request);
  const url = new URL(request.url);

  // Preserve query parameters (host, shop, etc.) for embedded app
  // The host parameter is base64-encoded and required for App Bridge initialization
  const searchParams = url.searchParams.toString();
  const redirectUrl = searchParams ? `/app?${searchParams}` : "/app";

  // Immediately redirect to app UI after authentication
  // Using the redirect function from authenticate.admin ensures proper
  // handling of embedded app parameters (host, shop, etc.)
  return redirect(redirectUrl);
};
