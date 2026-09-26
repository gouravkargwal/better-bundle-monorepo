import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useRouteLoaderData,
} from "@remix-run/react";
import { json } from "@remix-run/node";
import { type LoaderFunctionArgs } from "@remix-run/node";
import { getHostMode } from "./utils/host.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const mode = getHostMode(request);
  return json({ mode });
};

export function useMode() {
  return useRouteLoaderData<typeof loader>("root")?.mode ?? "marketing";
}

export default function Root() {
  return (
    <html lang="en" suppressHydrationWarning>
      <head suppressHydrationWarning>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body suppressHydrationWarning>
        <Outlet />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}
