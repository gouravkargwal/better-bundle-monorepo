import { BACKEND_URL } from "../config/constants";

class Logger {
  levels = {
    trace: 10,
    debug: 20,
    info: 30,
    warn: 40,
    error: 50,
    fatal: 60,
  };

  currentLevel;
  base;
  logBuffer = [];
  batchTimeout = null;
  batchSize;
  interval;
  backendUrl = BACKEND_URL;

  constructor(options = {}) {
    this.currentLevel = this.levels[options.level ?? "info"];
    this.base = {
      service: "venus-extension",
      env: "development",
      ...options.base ?? {},
    };
    this.batchSize = options.batchSize ?? 5;
    this.interval = options.interval ?? 3000;
  }

  createLogMethod(levelName, levelNum) {
    return (obj, msg, ...args) => {
      if (levelNum < this.currentLevel) return;

      const timestamp = new Date().toISOString();
      const logEntry = {
        level: levelNum,
        time: timestamp,
        ...this.base,
        ...(typeof obj === "object" && obj !== null ? obj : {}),
        msg: msg || (typeof obj === "string" ? obj : ""),
        ...(args.length > 0 ? { args } : {}),
      };

      // Console output
      const consoleMethod = levelName === "fatal" ? "error" : levelName;
      if (console[consoleMethod]) {
        (console[consoleMethod])(
          `[${levelName.toUpperCase()}]`,
          logEntry,
        );
      }

      // Send to backend
      this.sendToBackend(logEntry);
    };
  }

  async sendToBackend(logEntry) {
    this.logBuffer.push(logEntry);

    if (this.logBuffer.length >= this.batchSize) {
      await this.flushLogs();
    } else if (!this.batchTimeout) {
      this.batchTimeout = setTimeout(() => {
        this.flushLogs();
        this.batchTimeout = null;
      }, this.interval);
    }
  }

  async flushLogs() {
    if (this.logBuffer.length === 0) return;

    const baseUrl = this.backendUrl;
    const apiUrl = `${baseUrl}/logs`;

    await fetch(apiUrl, {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        logs: this.logBuffer,
        source: "mercury-extension",
        timestamp: new Date().toISOString(),
      }),
    });

    this.logBuffer = [];
  }

  trace = this.createLogMethod("trace", this.levels.trace);
  debug = this.createLogMethod("debug", this.levels.debug);
  info = this.createLogMethod("info", this.levels.info);
  warn = this.createLogMethod("warn", this.levels.warn);
  error = this.createLogMethod("error", this.levels.error);
  fatal = this.createLogMethod("fatal", this.levels.fatal);

  child(bindings) {
    return new Logger({
      level: "info", // Inherit from parent
      base: { ...this.base, ...bindings },
      batchSize: this.batchSize,
      interval: this.interval,
    });
  }

  async flush() {
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }
    await this.flushLogs();
  }
}

// Create and export a default logger instance
export const logger = new Logger({
  level: "info",
  base: {
    service: "mercury-extension",
    env: "development",
  },
  batchSize: 5,
  interval: 3000,
});

// Export the class for custom instances
export { Logger };
