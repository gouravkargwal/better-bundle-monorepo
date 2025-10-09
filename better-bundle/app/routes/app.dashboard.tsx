import type { LoaderFunctionArgs } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";
import { useLoaderData, Outlet } from "@remix-run/react";
import { DashboardPage } from "../features/dashboard/components/DashboardPage";
import { getDateRangeFromUrl } from "../utils/datetime";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);

  // If accessing /app/dashboard directly, redirect to revenue tab
  if (url.pathname === "/app/dashboard") {
    const params = new URLSearchParams(url.search);
    const queryString = params.toString();
    const query = queryString ? `?${queryString}` : "";

    return redirect(`/app/dashboard/revenue${query}`);
  }

  const { startDate, endDate } = getDateRangeFromUrl(url);
  return json({ startDate, endDate });
};

export default function Dashboard() {
  const { startDate, endDate } = useLoaderData<typeof loader>();
  return (
    <DashboardPage startDate={startDate} endDate={endDate}>
      <Outlet />
    </DashboardPage>
  );
}
