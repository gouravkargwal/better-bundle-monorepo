import { NavMenu } from "@shopify/app-bridge-react";
import { Link } from "@remix-run/react";

/**
 * The merchant navigation.
 *
 * Six items, down from seven. Two changes worth explaining:
 *
 * - **Preview merged into Setup.** Previewing is the "did my install work"
 *   check — the same task as installing, minutes later — and it was holding a
 *   permanent slot for something a merchant does once.
 * - **Impact renamed Proof.** The page answers one question ("would I have got
 *   those sales anyway?"), and "Impact" was vague enough that it overlapped
 *   with Overview in merchants' heads as well as in the code.
 *
 * Labels are the information architecture; the paths behind them are unchanged.
 * In an embedded app the merchant never sees a URL, so renaming routes would
 * cost redirect stubs and every internal link while buying nothing.
 *
 * `useLocation` and the old `NavItem` wrapper are gone: App Bridge's `NavMenu`
 * derives the active item itself, and `NavItem` accepted an `isActive` prop
 * that it then ignored — so every one of those computed booleans was dead.
 */

interface EnhancedNavMenuProps {
  isOnboarded: boolean;
}

export function EnhancedNavMenu({ isOnboarded }: EnhancedNavMenuProps) {
  if (!isOnboarded) {
    return (
      <NavMenu>
        <Link to="/app/onboarding" rel="home" prefetch="intent">
          Get started
        </Link>
        <Link to="/app/help" prefetch="intent">
          Help &amp; support
        </Link>
      </NavMenu>
    );
  }

  return (
    <NavMenu>
      {/* App Bridge treats the first child as the home link. */}
      <Link to="/app/overview" rel="home" prefetch="intent">
        Home
      </Link>
      <Link to="/app/impact" prefetch="intent">
        Proof
      </Link>
      <Link to="/app/extensions" prefetch="intent">
        Setup
      </Link>
      <Link to="/app/billing" prefetch="intent">
        Billing
      </Link>
      <Link to="/app/settings" prefetch="intent">
        Settings
      </Link>
      <Link to="/app/help" prefetch="intent">
        Help &amp; support
      </Link>
    </NavMenu>
  );
}
