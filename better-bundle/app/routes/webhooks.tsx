import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);
  if (!url.hostname.startsWith("app.")) {
    throw new Response("Not Found", { status: 404 });
  }
  return json({});
};
