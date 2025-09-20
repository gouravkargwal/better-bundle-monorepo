import { NavMenu } from "@shopify/app-bridge-react";
import { useLocation } from "@remix-run/react";
import NavItem from "./NavItem";

export function EnhancedNavMenu() {
  const location = useLocation();

  console.log("🔍 EnhancedNavMenu - rendering with path:", location.pathname);

  return (
    <div style={{ padding: "16px 0" }}>
      <NavMenu>
        <NavItem to="/app" isActive={location.pathname === "/app"}>
          Home
        </NavItem>

        <NavItem
          to="/app/dashboard"
          isActive={location.pathname === "/app/dashboard"}
        >
          Analytics Dashboard
        </NavItem>

        <NavItem
          to="/app/widget-config"
          isActive={location.pathname === "/app/widget-config"}
        >
          Extensions
        </NavItem>

        <NavItem
          to="/app/billing"
          isActive={location.pathname === "/app/billing"}
        >
          Billing & Performance
        </NavItem>

        <NavItem to="/app/help" isActive={location.pathname === "/app/help"}>
          Help & Support
        </NavItem>
      </NavMenu>
    </div>
  );
}
