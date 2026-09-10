import { json } from "@remix-run/node";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { TitleBar } from "@shopify/app-bridge-react";

import { routeErrorBoundary } from "../components/UI/RouteError";
import { ProofPage } from "../features/impact/components/ProofPage";
import {
  getLiftBySurface,
  getLiftSummary,
} from "../features/impact/services/lift.service";
import type { ProofResult, SurfaceProofRow } from "../features/impact/types/proof.types";
import prisma from "../db.server";
import { authenticate } from "../shopify.server";

/**
 * The Proof page.
 *
 * Was 521 lines with three tab components, a hand-rolled CSS bar chart and a
 * rule engine, all inline, rendering fabricated statistics. The statistics now
 * come from the python-worker incrementality engine, which returns a state
 * rather than a number when it cannot honestly produce one.
 */

const WINDOW_DAYS = 30;

interface ProofLoaderData {
  summary: ProofResult;
  bySurface: SurfaceProofRow[];
  currencyCode: string;
  holdoutPercent: number;
  windowDays: number;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  const shop = await prisma.shops.findUnique({
    where: { shop_domain: session.shop },
    select: { id: true, currency_code: true, holdout_disabled: true },
  });

  // Throw rather than return an error object: the route ErrorBoundary renders
  // it once, in Polaris, instead of every component narrowing on `"error" in
  // data` and inventing its own presentation.
  if (!shop) {
    throw new Response("Shop not found", { status: 404 });
  }

  const [summary, bySurface] = await Promise.all([
    getLiftSummary(shop.id),
    getLiftBySurface(shop.id),
  ]);

  return json<ProofLoaderData>({
    summary,
    bySurface,
    currencyCode: (shop.currency_code || "USD").toUpperCase(),
    // Mirrors INITIAL_HOLDOUT_PERCENT in holdout_service.py. Used for copy
    // only ("the 10% who didn't"); the engine decides measurability itself.
    holdoutPercent: shop.holdout_disabled ? 0 : 10,
    windowDays: WINDOW_DAYS,
  });
};

export default function Proof() {
  const data = useLoaderData<typeof loader>() as ProofLoaderData;

  return (
    <>
      <TitleBar title="Proof" />
      <ProofPage
        summary={data.summary}
        bySurface={data.bySurface}
        currencyCode={data.currencyCode}
        holdoutPercent={data.holdoutPercent}
        windowDays={data.windowDays}
      />
    </>
  );
}

export const ErrorBoundary = routeErrorBoundary;
