import pino from "pino";

const isDevelopment = process.env.NODE_ENV === "development";
const isProduction = process.env.NODE_ENV === "production";
const useGrafana = process.env.GRAFANA_LOKI_ENABLED === "true" || isProduction;

// Create Pino logger with environment-based transport
const logger = pino(
  {
    level: process.env.LOG_LEVEL || (isDevelopment ? "debug" : "info"),
    base: {
      service: "remix-app",
      env: process.env.NODE_ENV || "development",
    },
  },
  useGrafana
    ? pino.transport({
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
      })
    : pino.transport({
        target: "pino/file",
        options: { destination: 1 }, // stdout
      }),
);

export default logger;
