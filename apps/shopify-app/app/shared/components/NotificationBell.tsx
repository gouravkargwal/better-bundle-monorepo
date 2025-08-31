import React, { useState, useEffect } from "react";
import {
  Button,
  Popover,
  ActionList,
  Badge,
  Text,
  BlockStack,
  InlineStack,
} from "@shopify/polaris";
import { useFetcher } from "@remix-run/react";

interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  actionUrl?: string;
  isRead: boolean;
  createdAt: string;
  metadata?: any;
}

export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  
  const notificationsFetcher = useFetcher();
  const countFetcher = useFetcher();

  // Load unread count on mount
  useEffect(() => {
    countFetcher.load("/api/notifications?action=count");
  }, []);

  // Load notifications when popover opens
  useEffect(() => {
    if (isOpen) {
      notificationsFetcher.load("/api/notifications?action=unread");
    }
  }, [isOpen]);

  // Handle count response
  useEffect(() => {
    if (countFetcher.data?.success) {
      setUnreadCount(countFetcher.data.count);
    }
  }, [countFetcher.data]);

  // Handle notifications response
  useEffect(() => {
    if (notificationsFetcher.data?.success) {
      setNotifications(notificationsFetcher.data.notifications);
    }
  }, [notificationsFetcher.data]);

  const handleMarkAsRead = async (notificationId: string) => {
    const formData = new FormData();
    formData.append("action", "mark-read");
    formData.append("notificationId", notificationId);

    notificationsFetcher.submit(formData, {
      method: "POST",
      action: "/api/notifications",
    });

    // Optimistically update UI
    setNotifications((prev) =>
      prev.map((n) => (n.id === notificationId ? { ...n, isRead: true } : n)),
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));
  };

  const handleMarkAllAsRead = async () => {
    const formData = new FormData();
    formData.append("action", "mark-all-read");

    notificationsFetcher.submit(formData, {
      method: "POST",
      action: "/api/notifications",
    });

    // Optimistically update UI
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
    setUnreadCount(0);
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor(
      (now.getTime() - date.getTime()) / (1000 * 60),
    );

    if (diffInMinutes < 1) return "Just now";
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;

    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) return `${diffInHours}h ago`;

    const diffInDays = Math.floor(diffInHours / 24);
    return `${diffInDays}d ago`;
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case "analysis_complete":
        return "✅";
      case "analysis_failed":
        return "❌";
      case "analysis_started":
        return "🔄";
      default:
        return "📢";
    }
  };

  return (
    <Popover
      active={isOpen}
      activator={
        <Button
          onClick={() => setIsOpen(!isOpen)}
          accessibilityLabel="Notifications"
          variant="tertiary"
        >
          🔔
          {unreadCount > 0 && (
            <Badge tone="critical">
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
      }
      onClose={() => setIsOpen(false)}
    >
      <div style={{ width: "400px", maxHeight: "500px", overflow: "auto" }}>
        <BlockStack gap="400">
          <div style={{ padding: "16px", borderBottom: "1px solid #e1e5e9" }}>
            <InlineStack align="space-between">
              <Text variant="headingMd" as="h3">
                Notifications
              </Text>
              {unreadCount > 0 && (
                <Button
                  variant="tertiary"
                  onClick={handleMarkAllAsRead}
                >
                  Mark all read
                </Button>
              )}
            </InlineStack>
          </div>

          {notificationsFetcher.state === "loading" ? (
            <div style={{ padding: "16px", textAlign: "center" }}>
              <Text tone="subdued" as="p">Loading notifications...</Text>
            </div>
          ) : notifications.length === 0 ? (
            <div style={{ padding: "16px", textAlign: "center" }}>
              <Text tone="subdued" as="p">No unread notifications</Text>
            </div>
          ) : (
            <ActionList
              actionRole="menuitem"
              items={notifications.map((notification) => ({
                content: (
                  <div style={{ width: "100%" }}>
                    <BlockStack gap="200">
                      <InlineStack align="space-between">
                        <InlineStack gap="200" align="baseline">
                          <Text variant="bodyMd" as="span">
                            {getNotificationIcon(notification.type)}{" "}
                            {notification.title}
                          </Text>
                          <Text variant="bodySm" as="span" tone="subdued">
                            {formatTimeAgo(notification.createdAt)}
                          </Text>
                        </InlineStack>
                        {!notification.isRead && (
                          <Badge tone="info">
                            New
                          </Badge>
                        )}
                      </InlineStack>
                      <Text variant="bodySm" as="p" tone="subdued">
                        {notification.message}
                      </Text>
                      {notification.actionUrl && (
                        <Button
                          variant="tertiary"
                          url={notification.actionUrl}
                          onClick={() => setIsOpen(false)}
                        >
                          View Details
                        </Button>
                      )}
                    </BlockStack>
                  </div>
                ),
                onAction: () => {
                  if (!notification.isRead) {
                    handleMarkAsRead(notification.id);
                  }
                  if (notification.actionUrl) {
                    window.location.href = notification.actionUrl;
                  }
                },
              }))}
            />
          )}
        </BlockStack>
      </div>
    </Popover>
  );
}
