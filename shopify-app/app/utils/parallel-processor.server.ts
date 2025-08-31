// Parallel processing utility for bundle analysis
import { logger } from './logger.server';

export interface ProcessingTask<T> {
  id: string;
  data: T;
  priority?: number;
}

export interface ProcessingResult<T> {
  taskId: string;
  result: T;
  duration: number;
  success: boolean;
  error?: Error;
}

export interface ParallelProcessorConfig {
  maxConcurrency: number;
  batchSize: number;
  timeoutMs: number;
  retryAttempts: number;
}

export class ParallelProcessor {
  private config: ParallelProcessorConfig;

  constructor(config: Partial<ParallelProcessorConfig> = {}) {
    this.config = {
      maxConcurrency: 4,
      batchSize: 100,
      timeoutMs: 30000,
      retryAttempts: 2,
      ...config,
    };
  }

  /**
   * Process tasks in parallel with controlled concurrency
   */
  async processInParallel<T, R>(
    tasks: ProcessingTask<T>[],
    processor: (task: ProcessingTask<T>) => Promise<R>,
    operationName: string = 'parallel-processing'
  ): Promise<ProcessingResult<R>[]> {
    logger.startTimer(operationName);
    logger.info(`Starting parallel processing of ${tasks.length} tasks`, {
      maxConcurrency: this.config.maxConcurrency,
      batchSize: this.config.batchSize,
    });

    const results: ProcessingResult<R>[] = [];
    const batches = this.createBatches(tasks, this.config.batchSize);

    for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
      const batch = batches[batchIndex];
      logger.info(`Processing batch ${batchIndex + 1}/${batches.length}`, {
        batchSize: batch.length,
        totalProcessed: results.length,
      });

      const batchResults = await this.processBatch(batch, processor, operationName);
      results.push(...batchResults);
    }

    const duration = logger.endTimer(operationName, {
      totalTasks: tasks.length,
      totalResults: results.length,
      successfulResults: results.filter(r => r.success).length,
    });

    logger.logPerformance(operationName, {
      totalTasks: tasks.length,
      totalDuration: duration,
      averageTimePerTask: duration / tasks.length,
      throughput: (tasks.length / duration) * 1000, // tasks per second
    });

    return results;
  }

  /**
   * Process a batch of tasks with controlled concurrency
   */
  private async processBatch<T, R>(
    tasks: ProcessingTask<T>[],
    processor: (task: ProcessingTask<T>) => Promise<R>,
    operationName: string
  ): Promise<ProcessingResult<R>[]> {
    const results: ProcessingResult<R>[] = [];
    const semaphore = new Semaphore(this.config.maxConcurrency);

    const promises = tasks.map(async (task) => {
      return semaphore.acquire().then(async () => {
        const startTime = Date.now();
        let attempts = 0;
        let lastError: Error | undefined;

        while (attempts <= this.config.retryAttempts) {
          try {
            const result = await Promise.race([
              processor(task),
              this.createTimeout(this.config.timeoutMs),
            ]);

            const duration = Date.now() - startTime;
            return {
              taskId: task.id,
              result,
              duration,
              success: true,
            };
          } catch (error) {
            lastError = error instanceof Error ? error : new Error(String(error));
            attempts++;

            if (attempts <= this.config.retryAttempts) {
              logger.warn(`Retry ${attempts}/${this.config.retryAttempts} for task ${task.id}`, {
                taskId: task.id,
                error: lastError.message,
                operation: operationName,
              });
              await this.delay(Math.pow(2, attempts) * 100); // Exponential backoff
            }
          }
        }

        const duration = Date.now() - startTime;
        logger.error(`Task ${task.id} failed after ${this.config.retryAttempts} attempts`, {
          taskId: task.id,
          error: lastError?.message,
          duration,
          operation: operationName,
        });

        return {
          taskId: task.id,
          result: null as R,
          duration,
          success: false,
          error: lastError,
        };
      }).finally(() => {
        semaphore.release();
      });
    });

    const batchResults = await Promise.all(promises);
    results.push(...batchResults);

    return results;
  }

  /**
   * Create batches from tasks
   */
  private createBatches<T>(tasks: ProcessingTask<T>[], batchSize: number): ProcessingTask<T>[][] {
    const batches: ProcessingTask<T>[][] = [];
    for (let i = 0; i < tasks.length; i += batchSize) {
      batches.push(tasks.slice(i, i + batchSize));
    }
    return batches;
  }

  /**
   * Create a timeout promise
   */
  private createTimeout(ms: number): Promise<never> {
    return new Promise((_, reject) => {
      setTimeout(() => reject(new Error(`Operation timed out after ${ms}ms`)), ms);
    });
  }

  /**
   * Delay utility
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Process bundle analysis in parallel
   */
  async processBundleAnalysis<T>(
    bundles: T[],
    processor: (bundle: T, index: number) => Promise<any>,
    operationName: string = 'bundle-analysis'
  ): Promise<any[]> {
    const tasks: ProcessingTask<T>[] = bundles.map((bundle, index) => ({
      id: `bundle-${index}`,
      data: bundle,
      priority: index, // Process in order
    }));

    const results = await this.processInParallel(tasks, async (task) => {
      return processor(task.data, parseInt(task.id.split('-')[1]));
    }, operationName);

    return results
      .filter(r => r.success)
      .map(r => r.result);
  }
}

/**
 * Semaphore for controlling concurrency
 */
class Semaphore {
  private permits: number;
  private waitQueue: Array<() => void> = [];

  constructor(permits: number) {
    this.permits = permits;
  }

  async acquire(): Promise<void> {
    if (this.permits > 0) {
      this.permits--;
      return Promise.resolve();
    }

    return new Promise<void>((resolve) => {
      this.waitQueue.push(resolve);
    });
  }

  release(): void {
    this.permits++;
    if (this.waitQueue.length > 0) {
      const next = this.waitQueue.shift();
      if (next) {
        this.permits--;
        next();
      }
    }
  }
}

// Export singleton instance with default configuration
export const parallelProcessor = new ParallelProcessor({
  maxConcurrency: 4,
  batchSize: 100,
  timeoutMs: 30000,
  retryAttempts: 2,
});
