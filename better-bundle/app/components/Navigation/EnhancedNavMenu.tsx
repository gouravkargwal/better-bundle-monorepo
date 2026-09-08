import { NavMenu } from "@shopify/app-bridge-react";
import { useLocation } from "@remix-run/react";
import NavItem from "./NavItem";

interface EnhancedNavMenuProps {
  isOnboarded: boolean;
}

export function EnhancedNavMenu({ isOnboarded }: EnhancedNavMenuProps) {
  const location = useLocation();

  // Not onboarded → show minimal nav
  if (!isOnboarded) {
    return (
      <NavMenu>
        <NavItem
          to="/app/onboarding"
          isActive={location.pathname === "/app/onboarding"}
          prefetch="intent"
        >
          Get Started
        </NavItem>

        <NavItem
          to="/app/help"
          isActive={location.pathname === "/app/help"}
          prefetch="intent"
        >
          Help & Support
        </NavItem>
      </NavMenu>
    );
  }

  // Onboarded → show full menu
  return (
    <NavMenu>
      <NavItem
        to="/app/overview"
        isActive={location.pathname === "/app/overview"}
        prefetch="intent"
      >
        Overview
      </NavItem>

      <NavItem
        to="/app/impact"
        isActive={location.pathname.startsWith("/app/impact")}
        prefetch="intent"
      >
        Impact
      </NavItem>

      <NavItem
        to="/app/extensions"
        isActive={location.pathname === "/app/extensions"}
        prefetch="intent"
      >
        Extensions
      </NavItem>

      <NavItem
        to="/app/preview"
        isActive={location.pathname === "/app/preview"}
        prefetch="intent"
      >
        Preview
      </NavItem>

      <NavItem
        to="/app/billing"
        isActive={location.pathname.startsWith("/app/billing")}
        prefetch="intent"
      >
        Billing
      </NavItem>

      <NavItem
        to="/app/settings"
        isActive={location.pathname === "/app/settings"}
        prefetch="intent"
      >
        Settings
      </NavItem>

      <NavItem
        to="/app/help"
        isActive={location.pathname === "/app/help"}
        prefetch="intent"
      >
        Help & Support
      </NavItem>
    </NavMenu>
  );
}
