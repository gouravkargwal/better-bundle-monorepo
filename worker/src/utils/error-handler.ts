/**
 * Centralized error handling utility for the Fly.io worker
 * Converts technical errors into user-friendly messages
 */

export interface ErrorContext {
  operation: string;
  shopId?: string;
  jobId?: string;
}

export class ErrorHandler {
  /**
   * Convert technical errors to user-friendly messages
   */
  static toUserFriendlyError(error: any, context?: ErrorContext): string {
    console.error(`❌ Error in ${context?.operation || 'unknown operation'}:`, {
      message: error.message,
      code: error.code,
      status: error.response?.status,
      shopId: context?.shopId,
      jobId: context?.jobId,
    });

    // Handle specific database constraint errors
    if (error.code === 'P2003') {
      return "Unable to save store data. Please try again or contact support if the issue persists.";
    }

    // Handle other Prisma errors
    if (error.code && error.code.startsWith('P')) {
      return "Database error occurred. Please try again.";
    }

    // Handle network errors
    if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
      return "Unable to connect to your store. Please check your internet connection and try again.";
    }

    // Handle Shopify API errors
    if (error.response?.status === 401) {
      return "Store access token is invalid. Please reconnect your store.";
    }

    if (error.response?.status === 403) {
      return "Insufficient permissions to access store data. Please check your app permissions.";
    }

    if (error.response?.status === 404) {
      return "Store not found. Please check your store URL and try again.";
    }

    if (error.response?.status >= 500) {
      return "Shopify service is temporarily unavailable. Please try again in a few minutes.";
    }

    // Handle timeout errors
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return "Request timed out. Please try again.";
    }

    // Generic error for other cases
    return "An unexpected error occurred. Please try again or contact support if the issue persists.";
  }

  /**
   * Check if error is retryable
   */
  static isRetryableError(error: any): boolean {
    // Network errors are usually retryable
    if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
      return true;
    }

    // Timeout errors are retryable
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return true;
    }

    // 5xx server errors are retryable
    if (error.response?.status >= 500) {
      return true;
    }

    // Rate limiting errors are retryable
    if (error.response?.status === 429) {
      return true;
    }

    return false;
  }

  /**
   * Get error severity for logging
   */
  static getErrorSeverity(error: any): 'low' | 'medium' | 'high' {
    // Database constraint errors are high severity
    if (error.code === 'P2003') {
      return 'high';
    }

    // Authentication errors are high severity
    if (error.response?.status === 401) {
      return 'high';
    }

    // Network errors are medium severity
    if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
      return 'medium';
    }

    // Timeout errors are medium severity
    if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      return 'medium';
    }

    // 5xx server errors are medium severity
    if (error.response?.status >= 500) {
      return 'medium';
    }

    return 'low';
  }
}
