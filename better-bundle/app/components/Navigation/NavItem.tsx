import { Link, type LinkProps } from "@remix-run/react";
import type { ReactNode } from "react";

interface NavItemProps extends LinkProps {
  isActive: boolean;
  children: ReactNode;
}

export default function NavItem({
  to,
  isActive,
  children,
  prefetch = "intent",
  ...props
}: NavItemProps) {
  return (
    <Link
      to={to}
      prefetch={prefetch} // Prefetch on hover/intent
      {...props}
    >
      {children}
    </Link>
  );
}
