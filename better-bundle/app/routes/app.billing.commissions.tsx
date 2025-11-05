import { redirect } from "@remix-run/node";
import type { LoaderFunctionArgs } from "@remix-run/node";

// Redirect old commission records route to invoices (usage charges)
export async function loader({ request }: LoaderFunctionArgs) {
  return redirect("/app/billing/invoices");
}
