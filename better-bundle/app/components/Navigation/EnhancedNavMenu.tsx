import { NavMenu } from "@shopify/app-bridge-react";
import { useLocation } from "@remix-run/react";
import NavItem from "./NavItem";

export function EnhancedNavMenu() {
  const location = useLocation();

  console.log("🔍 EnhancedNavMenu - rendering with path:", location.pathname);

  return (
    <div style={{ padding: "16px 0" }}>
      <NavMenu>
        <NavItem
          to="/app/dashboard"
          isActive={location.pathname === "/app/dashboard"}
        >
          Dashboard
        </NavItem>

        <NavItem
          to="/app/extensions"
          isActive={location.pathname === "/app/extensions"}
        >
          Extensions
        </NavItem>

        <NavItem
          to="/app/billing"
          isActive={location.pathname === "/app/billing"}
        >
          Billing
        </NavItem>

        <NavItem to="/app/help" isActive={location.pathname === "/app/help"}>
          Help & Support
        </NavItem>
      </NavMenu>
    </div>
  );
}
