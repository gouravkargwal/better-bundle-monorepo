/**
 * Logging middleware for Remix app
 * Automatically logs requests, responses, and errors
 */

import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { logger } from "~/utils/server-logger";

export function withLogging<T extends LoaderFunctionArgs | ActionFunctionArgs>(
  handler: (args: T) => Promise<any>,
) {
  return async (args: T) => {
    const startTime = Date.now();
    const { request } = args;
    const url = new URL(request.url);
    const route = url.pathname;

    try {
      // Log request start
      if (request.method === "GET") {
        logger.loaderStart(route, request);
      } else {
        logger.actionStart(route, request);
      }

      // Execute the handler
      const result = await handler(args);

      // Log successful completion
      const duration = Date.now() - startTime;
      if (request.method === "GET") {
        logger.loaderEnd(route, duration);
      } else {
        logger.actionEnd(route, duration);
      }

      return result;
    } catch (error) {
      // Log error
      const duration = Date.now() - startTime;
      logger.error(
        {
          route,
          method: request.method,
          duration,
          url: request.url,
        },
        `Request failed: ${route}`,
        error,
      );

      throw error;
    }
  };
}

export function withWebhookLogging<
  T extends LoaderFunctionArgs | ActionFunctionArgs,
>(handler: (args: T) => Promise<any>, webhookName: string) {
  return async (args: T) => {
    const startTime = Date.now();
    const { request } = args;

    try {
      // Log webhook received
      logger.webhookReceived(webhookName, request);

      // Execute the handler
      const result = await handler(args);

      // Log successful completion
      const duration = Date.now() - startTime;
      logger.info(
        {
          webhook: webhookName,
          duration,
          method: request.method,
          url: request.url,
        },
        `Webhook processed: ${webhookName}`,
      );

      return result;
    } catch (error) {
      // Log error
      const duration = Date.now() - startTime;
      logger.error(
        {
          webhook: webhookName,
          method: request.method,
          duration,
          url: request.url,
        },
        `Webhook failed: ${webhookName}`,
        error,
      );

      throw error;
    }
  };
}
