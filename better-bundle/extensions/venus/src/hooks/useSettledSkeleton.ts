import { useEffect, useState } from "react";

/**
 * Should a loading skeleton be painted at all?
 *
 * A skeleton is a promise that something is coming. We cannot keep that promise
 * until the response is in: a shopper may be in the holdout, the surface may be
 * switched off, or this product may simply have no recommendations. Painting one
 * immediately and then removing it looks like a widget that crashed — which is
 * worse than never having shown anything.
 *
 * So the skeleton is withheld for `delayMs`. The API answers in roughly 130ms,
 * so the overwhelming majority of loads resolve inside the window and the
 * shopper sees exactly one transition: nothing, then recommendations (or
 * nothing at all). The skeleton only appears when the wait has genuinely become
 * long enough that silence would read as breakage — which is the only case it
 * was ever earning its keep.
 *
 * This is the JS-surface counterpart to the metafield gate on the storefront
 * block. Phoenix needs a metafield because Liquid has to commit to markup
 * before it can ask anything; these extensions resolve before they paint, so
 * they only need to wait.
 */
export function useSettledSkeleton(loading: boolean, delayMs = 400): boolean {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!loading) {
      setShow(false);
      return;
    }

    const timer = setTimeout(() => setShow(true), delayMs);
    return () => clearTimeout(timer);
  }, [loading, delayMs]);

  return show;
}
