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

  const getSystemStatusBadge = () => {
    if (!systemStatus) return null;

    switch (systemStatus.health) {
      case "healthy":
        return {
          content: "All Systems Active",
          tone: "success" as const,
        };
      case "warning":
        return {
          content: "Some Issues",
          tone: "warning" as const,
        };
      case "critical":
        return {
          content: "System Issues",
          tone: "critical" as const,
        };
      default:
        return null;
    }
  };

  const getExtensionsBadge = () => {
    if (!systemStatus) return null;

    const activeCount = systemStatus.extensionsActive;
    const totalCount = systemStatus.totalExtensions;

    if (activeCount === totalCount) {
      return {
        content: "All Active",
        tone: "success" as const,
      };
    } else if (activeCount > 0) {
      return {
        content: `${activeCount}/${totalCount} Active`,
        tone: "warning" as const,
      };
    } else {
      return {
        content: "Not Configured",
        tone: "critical" as const,
      };
    }
  };

  const systemBadge = getSystemStatusBadge();
  const extensionsBadge = getExtensionsBadge();

  return (
    <div style={{ padding: "16px 0" }}>
      <NavMenu>
        {/* System Status Header */}
        {systemStatus && (
          <div
            style={{
              padding: "12px 16px",
              marginBottom: "8px",
              backgroundColor: "#F6F6F7",
              borderRadius: "8px",
              border: "1px solid #E1E3E5",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "4px",
              }}
            >
              <span style={{ fontSize: "14px", fontWeight: "600" }}>
                System Status
              </span>
              {systemBadge ? (
                <Badge tone={systemBadge.tone} size="small">
                  {systemBadge.content}
                </Badge>
              ) : null}
            </div>
            <div style={{ fontSize: "12px", color: "#6B7280" }}>
              Extensions: {systemStatus.extensionsActive}/
              {systemStatus.totalExtensions} active
            </div>
          </div>
        )}

        {/* Navigation Items */}
        <NavItem to="/app" isActive={location.pathname === "/app"}>
          Home
        </NavItem>

        <NavItem
          to="/app/dashboard"
          badge={systemBadge ?? undefined}
          isActive={location.pathname === "/app/dashboard"}
        >
          Analytics Dashboard
        </NavItem>

        <NavItem
          to="/app/widget-config"
          badge={extensionsBadge ?? undefined}
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
