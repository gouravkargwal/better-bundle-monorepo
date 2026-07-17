declare module "*.css";

// Allow style prop on Polaris components that support it at runtime
// but whose TypeScript types don't include it explicitly.
declare module "@shopify/polaris" {
  export interface BadgeProps {
    style?: React.CSSProperties;
  }
  export interface TextProps {
    style?: React.CSSProperties;
  }
}

