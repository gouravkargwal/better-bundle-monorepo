/**
 * Phoenix Logger using Pino with Loki and Pretty
 * Browser-compatible Pino logger with Grafana Loki integration
 */

// Phoenix logging configuration
const PHOENIX_LOGGING_CONFIG = {
  level: "info",
  format: "console", // or "json" for production
  loki: {
    enabled: true, // Set to true for Grafana
    url: "https://nonconscientious-annette-saddeningly.ngrok-free.dev:3100", // Your Loki endpoint
    labels: {
      service: "phoenix-extension",
      env: "development",
    },
  },
  console: {
    enabled: true,
    colorize: true,
    translateTime: "SYS:standard",
    singleLine: false,
  },
};

// Wait for Pino to be available
function waitForPino() {
  return new Promise((resolve) => {
    if (typeof window.pino !== "undefined") {
      resolve(window.pino);
    } else {
      setTimeout(() => waitForPino().then(resolve), 100);
    }
  });
}

// Create Pino logger instance
async function createPhoenixLogger() {
  const pino = await waitForPino();

  // Create transport configuration
  const transport = PHOENIX_LOGGING_CONFIG.loki.enabled
    ? {
      target: "pino-loki",
      options: {
        batching: true,
        interval: 5,
        host: PHOENIX_LOGGING_CONFIG.loki.url,
        labels: PHOENIX_LOGGING_CONFIG.loki.labels,
      },
    }
    : {
      target: "pino-pretty",
      options: {
        colorize: PHOENIX_LOGGING_CONFIG.console.colorize,
        translateTime: PHOENIX_LOGGING_CONFIG.console.translateTime,
        ignore: "pid,hostname",
        singleLine: PHOENIX_LOGGING_CONFIG.console.singleLine,
      },
    };

  // Create Pino logger
  const logger = pino({
    level: PHOENIX_LOGGING_CONFIG.level,
    transport: PHOENIX_LOGGING_CONFIG.loki.enabled ? transport : undefined,
    base: {
      service: PHOENIX_LOGGING_CONFIG.loki.labels.service,
      env: PHOENIX_LOGGING_CONFIG.loki.labels.env,
    },
  });

  return logger;
}

// Initialize logger
let phoenixLogger = null;
let isInitializing = false;

// Create a smart fallback logger that can upgrade to the real logger
const createSmartLogger = () => {
  let realLogger = null;

  const smartLogger = {
    info: (...args) => {
      if (realLogger) {
        realLogger.info(...args);
      } else {
        console.info('[Phoenix]', ...args);
      }
    },
    warn: (...args) => {
      if (realLogger) {
        realLogger.warn(...args);
      } else {
        console.warn('[Phoenix]', ...args);
      }
    },
    error: (...args) => {
      if (realLogger) {
        realLogger.error(...args);
      } else {
        console.error('[Phoenix]', ...args);
      }
    },
    debug: (...args) => {
      if (realLogger) {
        realLogger.debug(...args);
      } else {
        console.debug('[Phoenix]', ...args);
      }
    },
    upgrade: (newLogger) => {
      realLogger = newLogger;
    }
  };

  return smartLogger;
};

// Create smart logger instance
const smartLogger = createSmartLogger();

// Initialize logger with retry mechanism
async function initializeLogger() {
  if (isInitializing) {
    return;
  }

  isInitializing = true;

  try {
    phoenixLogger = await createPhoenixLogger();
    smartLogger.upgrade(phoenixLogger);
    phoenixLogger.info(
      {
        event: "logger_initialized",
        service: "phoenix-extension",
      },
      "Phoenix: Logger initialized successfully",
    );
  } catch (error) {
    console.error("Failed to initialize Phoenix logger:", error);
    // Keep using smart logger with fallback
  }
}

// Set smart logger immediately
window.phoenixLogger = smartLogger;

// Initialize logger when DOM is ready
document.addEventListener("DOMContentLoaded", initializeLogger);

// Also try to initialize immediately in case DOM is already ready
if (document.readyState === 'loading') {
  // DOM is still loading, wait for DOMContentLoaded
} else {
  // DOM is already ready, initialize immediately
  initializeLogger();
}

// Export for use in other scripts
export default phoenixLogger;
