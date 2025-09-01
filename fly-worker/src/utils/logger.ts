export class Logger {
  static log(level: string, message: string, data?: any) {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      level,
      message,
      ...(data && { data }),
    };
    console.log(JSON.stringify(logEntry));
  }

  static info(message: string, data?: any) {
    this.log("INFO", message, data);
  }

  static warn(message: string, data?: any) {
    this.log("WARN", message, data);
  }

  static error(message: string, error?: any) {
    this.log("ERROR", message, {
      error: error?.message || error,
      stack: error?.stack,
      code: error?.code,
      hostname: error?.hostname,
      url: error?.config?.url,
    });
  }

  static debug(message: string, data?: any) {
    this.log("DEBUG", message, data);
  }

  static performance(operation: string, duration: number, data?: any) {
    this.log("PERFORMANCE", `${operation} completed in ${duration}ms`, data);
  }
}
