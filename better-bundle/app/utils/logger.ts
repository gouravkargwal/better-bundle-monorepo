import pino from "pino";

const isDevelopment = process.env.NODE_ENV === "development";

// Create Pino logger — OTel's PinoInstrumentation captures all logs for OpenObserve
const logger = pino(
  {
    level: process.env.LOG_LEVEL || (isDevelopment ? "debug" : "info"),
    base: {
      service: "remix-app",
      env: process.env.NODE_ENV || "development",
    },
  },
  pino.transport({
    target: "pino/file",
    options: { destination: 1 }, // stdout
  }),
);

export default logger;
