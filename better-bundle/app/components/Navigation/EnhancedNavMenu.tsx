import React from "react";
import { NavMenu } from "@shopify/app-bridge-react";
import { Link, useLocation } from "@remix-run/react";
import { Badge } from "@shopify/polaris";

interface NavItemProps {
  to: string;
  children: React.ReactNode;
  badge?: {
    content: string;
    tone: "success" | "warning" | "critical";
  };
  isActive?: boolean;
}

function NavItem({ to, children, badge, isActive }: NavItemProps) {
  return (
    <Link
      to={to}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "8px 12px",
        borderRadius: "6px",
        textDecoration: "none",
        color: isActive ? "#008060" : "#202223",
        backgroundColor: isActive ? "#F0FDF4" : "transparent",
        fontWeight: isActive ? "600" : "400",
        transition: "all 0.2s ease",
      }}
    >
      <span>{children}</span>
      {badge ? (
        <Badge tone={badge.tone} size="small">
          {badge.content}
        </Badge>
      ) : null}
    </Link>
  );
}

interface EnhancedNavMenuProps {
  systemStatus?: {
    health: "healthy" | "warning" | "critical";
    extensionsActive: number;
    totalExtensions: number;
  };
}

export function EnhancedNavMenu({ systemStatus }: EnhancedNavMenuProps) {
  const location = useLocation();

  return (
    <div style={{ padding: "16px 0" }}>
      <NavMenu>
        {/* Navigation Items */}
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
