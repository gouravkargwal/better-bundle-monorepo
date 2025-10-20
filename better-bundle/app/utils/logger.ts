/**
 * Pino Logger for BetterBundle Remix App
 * High-performance JSON logger with Grafana Loki integration
 */

import pino from "pino";

// Create Pino logger with Loki transport
const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  transport:
    process.env.GRAFANA_LOKI_ENABLED === "true"
      ? {
          target: "pino-loki",
          options: {
            batching: true,
            interval: 5,
            host: process.env.LOKI_URL || "http://loki:3100",
            labels: {
              service: "remix-app",
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
    service: "remix-app",
    env: process.env.NODE_ENV || "development",
  },
});

export default logger;
