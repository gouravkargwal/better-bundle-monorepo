import { NavMenu } from "@shopify/app-bridge-react";
import { useLocation } from "@remix-run/react";
import NavItem from "./NavItem";

interface EnhancedNavMenuProps {
  isOnboarded: boolean; // ⬅️ PROP ACCEPT KAR
}

export function EnhancedNavMenu({ isOnboarded }: EnhancedNavMenuProps) {
  const location = useLocation();

  // ⬅️ AGAR ONBOARDED NAHI HAI
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

  // ⬅️ AGAR ONBOARDED HAI - FULL MENU
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
        to="/app/dashboard"
        isActive={location.pathname === "/app/dashboard"}
        prefetch="intent"
      >
        Dashboard
      </NavItem>

      <NavItem
        to="/app/extensions"
        isActive={location.pathname === "/app/extensions"}
        prefetch="intent"
      >
        Extensions
      </NavItem>

      <NavItem
        to="/app/billing"
        isActive={location.pathname === "/app/billing"}
        prefetch="intent"
      >
        Billing
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
