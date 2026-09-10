import { redirect, type LoaderFunctionArgs } from "@remix-run/node";

/**
 * Preview moved onto the Setup page.
 *
 * Kept as a redirect rather than deleted outright: a merchant may have this
 * URL bookmarked or open in a tab, and the app's own notification banners have
 * linked here. Safe to delete once those are all gone.
 */
export const loader = async ({}: LoaderFunctionArgs) =>
  redirect("/app/extensions#preview", { status: 302 });
