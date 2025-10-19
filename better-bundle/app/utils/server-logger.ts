/**
 * Server-side Pino Logger for BetterBundle Remix App
 * High-performance JSON logger with Grafana Loki integration
 */

import pino from "pino";

// Create server Pino logger with Loki transport
const serverLogger = pino({
  level: process.env.LOG_LEVEL || "info",
  transport:
    process.env.GRAFANA_LOKI_ENABLED === "true"
      ? {
          target: "pino-loki",
          options: {
            batching: true,
            interval: 3,
            host: process.env.LOKI_URL || "http://loki:3100",
            labels: {
              service: "remix-app-server",
              env: process.env.NODE_ENV || "development",
            },
          },
        }
      : {
          target: "pino-pretty",
          options: {
            colorize: true,
            translateTime: "SYS:standard",
            ignore: "pid,hostname",
          },
        },
  base: {
    service: "remix-app-server",
    env: process.env.NODE_ENV || "development",
  },
});

// Add specialized logging methods for Remix
export const logger = {
  ...serverLogger,

  // Specialized logging methods for Remix
  loaderStart(route: string, request: Request, metadata?: Record<string, any>) {
    serverLogger.info(
      {
        route,
        method: request.method,
        url: request.url,
        userAgent: request.headers.get("user-agent"),
        ...metadata,
      },
      `Loader started: ${route}`,
    );
  },

  loaderEnd(route: string, duration: number, metadata?: Record<string, any>) {
    serverLogger.info(
      {
        route,
        duration,
        ...metadata,
      },
      `Loader completed: ${route}`,
    );
  },

  actionStart(
    action: string,
    request: Request,
    metadata?: Record<string, any>,
  ) {
    serverLogger.info(
      {
        action,
        method: request.method,
        url: request.url,
        userAgent: request.headers.get("user-agent"),
        ...metadata,
      },
      `Action started: ${action}`,
    );
  },

  actionEnd(action: string, duration: number, metadata?: Record<string, any>) {
    serverLogger.info(
      {
        action,
        duration,
        ...metadata,
      },
      `Action completed: ${action}`,
    );
  },

  webhookReceived(
    webhook: string,
    request: Request,
    metadata?: Record<string, any>,
  ) {
    serverLogger.info(
      {
        webhook,
        method: request.method,
        url: request.url,
        contentType: request.headers.get("content-type"),
        ...metadata,
      },
      `Webhook received: ${webhook}`,
    );
  },
};

export default logger;
