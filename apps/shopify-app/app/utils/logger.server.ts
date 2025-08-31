// Enhanced logging utility for bundle analysis
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

export interface LogContext {
  shopId?: string;
  bundleId?: string;
  operation?: string;
  duration?: number;
  bundleCount?: number;
  orderCount?: number;
  error?: Error;
}

export class BundleLogger {
  private static instance: BundleLogger;
  private logLevel: LogLevel = LogLevel.INFO;
  private startTimes: Map<string, number> = new Map();

  static getInstance(): BundleLogger {
    if (!BundleLogger.instance) {
      BundleLogger.instance = new BundleLogger();
    }
    return BundleLogger.instance;
  }

  setLogLevel(level: LogLevel): void {
    this.logLevel = level;
  }

  private formatMessage(level: LogLevel, message: string, context?: LogContext): string {
    const timestamp = new Date().toISOString();
    const levelStr = LogLevel[level];
    const contextStr = context ? ` [${JSON.stringify(context)}]` : '';
    return `[${timestamp}] ${levelStr}: ${message}${contextStr}`;
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.logLevel;
  }

  debug(message: string, context?: LogContext): void {
    if (this.shouldLog(LogLevel.DEBUG)) {
      console.debug(this.formatMessage(LogLevel.DEBUG, message, context));
    }
  }

  info(message: string, context?: LogContext): void {
    if (this.shouldLog(LogLevel.INFO)) {
      console.log(this.formatMessage(LogLevel.INFO, message, context));
    }
  }

  warn(message: string, context?: LogContext): void {
    if (this.shouldLog(LogLevel.WARN)) {
      console.warn(this.formatMessage(LogLevel.WARN, message, context));
    }
  }

  error(message: string, context?: LogContext): void {
    if (this.shouldLog(LogLevel.ERROR)) {
      console.error(this.formatMessage(LogLevel.ERROR, message, context));
    }
  }

  startTimer(operation: string): void {
    this.startTimes.set(operation, Date.now());
  }

  endTimer(operation: string, context?: LogContext): number {
    const startTime = this.startTimes.get(operation);
    if (startTime) {
      const duration = Date.now() - startTime;
      this.info(`${operation} completed in ${duration}ms`, { ...context, duration });
      this.startTimes.delete(operation);
      return duration;
    }
    return 0;
  }

  logBundleAnalysis(shopId: string, bundleCount: number, orderCount: number, duration: number): void {
    this.info('Bundle analysis completed', {
      shopId,
      bundleCount,
      orderCount,
      duration,
      operation: 'bundle-analysis',
    });
  }

  logBundleMetrics(bundleId: string, metrics: {
    support: number;
    confidence: number;
    lift: number;
    revenue: number;
  }): void {
    this.debug('Bundle metrics calculated', {
      bundleId,
      ...metrics,
      operation: 'bundle-metrics',
    });
  }

  logFilteringResults(
    operation: string,
    beforeCount: number,
    afterCount: number,
    context?: LogContext
  ): void {
    const filteredOut = beforeCount - afterCount;
    const percentage = beforeCount > 0 ? (filteredOut / beforeCount) * 100 : 0;
    
    this.info(`${operation} filtering completed`, {
      ...context,
      beforeCount,
      afterCount,
      filteredOut,
      percentage: Math.round(percentage * 100) / 100,
      operation: 'filtering',
    });
  }

  logError(operation: string, error: Error, context?: LogContext): void {
    this.error(`${operation} failed: ${error.message}`, {
      ...context,
      error,
      operation,
      stack: error.stack,
    });
  }

  logPerformance(operation: string, metrics: Record<string, number>): void {
    this.info(`Performance metrics for ${operation}`, {
      ...metrics,
      operation: 'performance',
    });
  }
}

// Export singleton instance
export const logger = BundleLogger.getInstance();
