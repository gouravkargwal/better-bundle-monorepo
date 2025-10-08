// app/utils/datetime.ts
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import relativeTime from "dayjs/plugin/relativeTime";

export const formatDate = (date: string | Date) => {
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

// Extend dayjs with plugins
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);

/**
 * Get user's timezone from browser
 */
export function getUserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/**
 * Convert UTC database time to user's timezone
 */
export function formatToUserTimezone(
  utcDate: Date | string,
  format: string = "MMM DD, YYYY HH:mm",
  userTimezone?: string,
): string {
  const timezone = userTimezone || getUserTimezone();
  return dayjs(utcDate).tz(timezone).format(format);
}

/**
 * Get relative time (e.g., "2 hours ago")
 */
export function getRelativeTime(utcDate: Date | string): string {
  return dayjs(utcDate).fromNow();
}

/**
 * Check if date is today
 */
export function isToday(
  utcDate: Date | string,
  userTimezone?: string,
): boolean {
  const timezone = userTimezone || getUserTimezone();
  return dayjs(utcDate).tz(timezone).isSame(dayjs().tz(timezone), "day");
}

/**
 * Check if date is yesterday
 */
export function isYesterday(
  utcDate: Date | string,
  userTimezone?: string,
): boolean {
  const timezone = userTimezone || getUserTimezone();
  return dayjs(utcDate)
    .tz(timezone)
    .isSame(dayjs().tz(timezone).subtract(1, "day"), "day");
}

/**
 * Format date for different contexts
 */
export function formatForContext(
  utcDate: Date | string,
  context: "dashboard" | "table" | "card" | "api",
  userTimezone?: string,
): string {
  const timezone = userTimezone || getUserTimezone();

  const formats = {
    dashboard: "MMM DD, HH:mm",
    table: "YYYY-MM-DD HH:mm",
    card: "MMM DD",
    api: "YYYY-MM-DD HH:mm:ss",
  };

  return dayjs(utcDate).tz(timezone).format(formats[context]);
}

/**
 * Get date range for queries
 */
export function getDateRange(period: string) {
  const now = dayjs();

  switch (period) {
    case "today":
      return {
        start: now.startOf("day").toISOString(),
        end: now.endOf("day").toISOString(),
      };
    case "yesterday":
      const yesterday = now.subtract(1, "day");
      return {
        start: yesterday.startOf("day").toISOString(),
        end: yesterday.endOf("day").toISOString(),
      };
    case "last_7_days":
      return {
        start: now.subtract(7, "day").startOf("day").toISOString(),
        end: now.endOf("day").toISOString(),
      };
    case "last_30_days":
      return {
        start: now.subtract(30, "day").startOf("day").toISOString(),
        end: now.endOf("day").toISOString(),
      };
    default:
      return {
        start: now.startOf("day").toISOString(),
        end: now.endOf("day").toISOString(),
      };
  }
}
