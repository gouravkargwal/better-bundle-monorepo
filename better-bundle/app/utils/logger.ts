import pino from "pino";

const isDevelopment = process.env.NODE_ENV === "development";
const isProduction = process.env.NODE_ENV === "production";
const useOpenObserve = Boolean(process.env.OPENOBSERVE_URL) || isProduction;

// Build pino-loki options
const lokiOptions: Record<string, any> = {
  batching: true,
  interval: 5,
  host: process.env.OPENOBSERVE_URL || "http://openobserve:5080",
  endpoint: "/api/default/loki/api/v1/push",
  labels: {
    service: "remix-app",
    env: process.env.NODE_ENV || "development",
  },
};

// Add basic auth if credentials are configured
const openObserveEmail = process.env.OPENOBSERVE_EMAIL;
const openObservePassword = process.env.OPENOBSERVE_PASSWORD;
if (openObserveEmail && openObservePassword) {
  lokiOptions.basicAuth = {
    username: openObserveEmail,
    password: openObservePassword,
  };
}

// Create Pino logger with environment-based transport
const logger = pino(
  {
    level: process.env.LOG_LEVEL || (isDevelopment ? "debug" : "info"),
    base: {
      service: "remix-app",
      env: process.env.NODE_ENV || "development",
    },
  },
  useOpenObserve
    ? pino.transport({
        target: "pino-loki",
        options: lokiOptions,
      })
    : pino.transport({
        target: "pino/file",
        options: { destination: 1 }, // stdout
      }),
);

export default logger;
