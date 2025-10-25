/**
 * Pino Logger for BetterBundle Remix App
 * High-performance JSON logger with Grafana Loki integration
 *
 * Environment-based configuration:
 * - Development: Pretty printed logs to console
 * - Production: Structured JSON logs to Grafana Loki
 */

import pino from "pino";

const isDevelopment = process.env.NODE_ENV === "development";
const isProduction = process.env.NODE_ENV === "production";
const useGrafana = process.env.GRAFANA_LOKI_ENABLED === "true" || isProduction;

// Create Pino logger with environment-based transport
const logger = pino({
  level: process.env.LOG_LEVEL || (isDevelopment ? "debug" : "info"),
  transport: useGrafana
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
          singleLine: false,
        },
      },
  base: {
    service: "remix-app",
    env: process.env.NODE_ENV || "development",
  },
});

export default logger;
