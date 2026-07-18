// Redirect route — /app/overview was replaced by /app/dashboard
import { redirect } from "@remix-run/node";
import type { LoaderFunctionArgs } from "@remix-run/node";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);
  const params = url.searchParams.toString();
  const query = params ? `?${params}` : "";
  return redirect(`/app/dashboard${query}`);
};
