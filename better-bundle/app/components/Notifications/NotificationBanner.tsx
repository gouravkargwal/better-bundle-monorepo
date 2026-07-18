import { Banner, BlockStack } from "@shopify/polaris";
import type { NotificationMessage } from "../../services/notification.service";

interface NotificationBannerProps {
  notifications: NotificationMessage[];
}

/**
 * Renders a stack of Polaris `Banner` components for each active notification.
 * When a notification includes an action, clicking it navigates the merchant.
 */
export function NotificationBanner({ notifications }: NotificationBannerProps) {
  if (!notifications || notifications.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        maxWidth: "var(--p-breakpoints-lg, 1200px)",
        marginInline: "auto",
        paddingBlock: "var(--p-space-2, 8px) 0",
        paddingInline: "var(--p-space-4, 16px)",
      }}
    >
      <BlockStack gap="200">
        {notifications.map((n) => (
          <Banner
            key={n.id}
            tone={n.type === "success" ? "success" : n.type}
            title={n.title}
            action={
              n.action
                ? {
                    content: n.action.label,
                    url: n.action.url,
                  }
                : undefined
            }
          >
            <p>{n.message}</p>
          </Banner>
        ))}
      </BlockStack>
    </div>
  );
}
