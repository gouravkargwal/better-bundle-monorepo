import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData, useOutletContext } from "@remix-run/react";

// Define the context type
type AppContext = {
  session: {
    id: string;
    shop: string;
    hasAccessToken: boolean;
  };
  shopId: string;
};

export const loader = async ({ request }: LoaderFunctionArgs) => {
  console.log("🔍 [TEST_COOKIES] Starting test cookies loader");
  
  // Log all request details
  const url = new URL(request.url);
  console.log("🔍 [TEST_COOKIES] Request URL:", url.pathname);
  console.log(
    "🔍 [TEST_COOKIES] Request headers:",
    Object.fromEntries(request.headers.entries()),
  );

  // Check cookies
  const cookieHeader = request.headers.get("cookie");
  console.log("🔍 [TEST_COOKIES] Cookie header:", cookieHeader);

  // No need to authenticate here - session comes from parent route
  console.log("🔍 [TEST_COOKIES] Using session from parent route context");

  return json({
    success: true,
    message: "Session data will come from parent route context",
    cookies: cookieHeader,
    headers: Object.fromEntries(request.headers.entries()),
  });
};

export default function TestCookies() {
  const data = useLoaderData<typeof loader>();
  const { session, shopId } = useOutletContext<AppContext>();
  
  return (
    <div style={{ padding: "20px", fontFamily: "monospace" }}>
      <h1>Cookie Test Route</h1>
      <h2>Loader Data:</h2>
      <pre>{JSON.stringify(data, null, 2)}</pre>
      
      <h2>Session from Context:</h2>
      <pre>{JSON.stringify({ session, shopId }, null, 2)}</pre>
    </div>
  );
}
