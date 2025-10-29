export interface LogEntry {
  level: number;
  time: string;
  service: string;
  env: string;
  msg: string;
  [key: string]: any;
}

export interface LoggerOptions {
  level?: LogLevel;
  base?: Record<string, any>;
  batchSize?: number;
  interval?: number;
}

export type LogLevel = "trace" | "debug" | "info" | "warn" | "error" | "fatal";

class Logger {
  private levels = {
    trace: 10,
    debug: 20,
    info: 30,
    warn: 40,
    error: 50,
    fatal: 60,
  };

  private currentLevel: number;
  private base: Record<string, any>;
  private logBuffer: LogEntry[] = [];
  private batchTimeout: NodeJS.Timeout | null = null;
  private batchSize: number;
  private interval: number;

  constructor(options: LoggerOptions = {}) {
    this.currentLevel = this.levels[options.level || "info"];
    this.base = {
      service: "apollo-extension",
      env: "development",
      ...options.base,
    };
    this.batchSize = options.batchSize || 5;
    this.interval = options.interval || 3000;
  }

  private createLogMethod(levelName: LogLevel, levelNum: number) {
    return (obj: any, msg?: string, ...args: any[]) => {
      if (levelNum < this.currentLevel) return;

      const timestamp = new Date().toISOString();
      const logEntry: LogEntry = {
        level: levelNum,
        time: timestamp,
        ...this.base,
        ...(typeof obj === "object" && obj !== null ? obj : {}),
        msg: msg || (typeof obj === "string" ? obj : ""),
        ...(args.length > 0 ? { args } : {}),
      };

      const consoleMethod = levelName === "fatal" ? "error" : levelName;
      if (console[consoleMethod as keyof Console]) {
        (console[consoleMethod as keyof Console] as Function)(
          `[${levelName.toUpperCase()}]`,
          logEntry,
        );
      }

      this.sendToBackend(logEntry);
    };
  }

  private async sendToBackend(logEntry: LogEntry) {
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

  private async flushLogs() {
    if (this.logBuffer.length === 0) return;

    const baseUrl = this.getBaseUrl();
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
        source: "apollo-extension",
        timestamp: new Date().toISOString(),
      }),
    });

    this.logBuffer = [];
  }

  private getBaseUrl(): string {
    if (typeof window !== "undefined" && (window as any).getBaseUrl) {
      return (window as any).getBaseUrl();
    }
    return "https://nonconscientious-annette-saddeningly.ngrok-free.dev";
  }

  public trace = this.createLogMethod("trace", this.levels.trace);
  public debug = this.createLogMethod("debug", this.levels.debug);
  public info = this.createLogMethod("info", this.levels.info);
  public warn = this.createLogMethod("warn", this.levels.warn);
  public error = this.createLogMethod("error", this.levels.error);
  public fatal = this.createLogMethod("fatal", this.levels.fatal);

  public child(bindings: Record<string, any>): Logger {
    return new Logger({
      level: "info",
      base: { ...this.base, ...bindings },
      batchSize: this.batchSize,
      interval: this.interval,
    });
  }

  public async flush(): Promise<void> {
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }
    await this.flushLogs();
  }
}

export const logger = new Logger({
  level: "info",
  base: {
    service: "apollo-extension",
    env: "development",
  },
  batchSize: 5,
  interval: 3000,
});

export { Logger };
