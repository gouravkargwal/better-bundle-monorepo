import { Link } from "@remix-run/react";
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

export default NavItem;
