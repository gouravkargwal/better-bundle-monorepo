import { PrismaClient } from "@prisma/client";
import { Logger } from "../utils/logger";
import {
  DatabaseOrder,
  DatabaseProduct,
  DatabaseCustomer,
} from "./shopify-api.service";

export interface ShopData {
  id: string;
  shopId: string;
  shopDomain: string;
  accessToken: string;
  planType: string;
  isActive: boolean;
  lastAnalysisAt: Date | null;
}

export interface DatabaseConfig {
  prisma: PrismaClient;
}

// Simple wrapper for database operations with lazy health check
export const withDatabaseHealthCheck = async <T>(
  config: DatabaseConfig,
  operation: () => Promise<T>,
  operationName: string,
  context?: Record<string, any>
): Promise<T> => {
  const startTime = Date.now();

  try {
    // Execute the operation directly - let it fail naturally if connection is bad
    const result = await operation();

    // Log performance
    const duration = Date.now() - startTime;
    Logger.performance(operationName, duration, context);

    return result;
  } catch (error) {
    // If it's a connection error, try to reconnect once
    if (error.message?.includes("connection") || error.code === "P1001") {
      Logger.warn(
        "Database connection error detected, attempting reconnection"
      );

      try {
        await reconnectDatabase(config);
        // Retry the operation once after reconnection
        const result = await operation();
        const duration = Date.now() - startTime;
        Logger.performance(
          `${operationName} (with reconnection)`,
          duration,
          context
        );
        return result;
      } catch (retryError) {
        Logger.error(
          `Failed to ${operationName.toLowerCase()} after reconnection`,
          {
            ...context,
            error: retryError,
          }
        );
        throw retryError;
      }
    }

    Logger.error(`Failed to ${operationName.toLowerCase()}`, {
      ...context,
      error,
    });
    throw error;
  }
};

// Health check for database connection
export const checkDatabaseHealth = async (
  config: DatabaseConfig
): Promise<boolean> => {
  try {
    // Simple query to test connection
    await config.prisma.$queryRaw`SELECT 1`;
    Logger.info("Database health check passed");
    return true;
  } catch (error) {
    Logger.error("Database health check failed", { error });
    return false;
  }
};

// Reconnect to database
export const reconnectDatabase = async (
  config: DatabaseConfig
): Promise<boolean> => {
  try {
    Logger.info("Attempting to reconnect to database");

    // Disconnect first
    await config.prisma.$disconnect();

    // Wait a moment
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Reconnect
    await config.prisma.$connect();

    // Test connection
    const isHealthy = await checkDatabaseHealth(config);

    if (isHealthy) {
      Logger.info("Database reconnection successful");
      return true;
    } else {
      Logger.error("Database reconnection failed - health check failed");
      return false;
    }
  } catch (error) {
    Logger.error("Database reconnection failed", { error });
    return false;
  }
};

// Get or create shop record
export const getOrCreateShop = async (
  config: DatabaseConfig,
  shopId: string,
  shopDomain: string,
  accessToken: string
): Promise<ShopData> => {
  return await withDatabaseHealthCheck(
    config,
    async () => {
      let shop = await config.prisma.shop.findUnique({
        where: { shopId },
      });

      if (!shop) {
        Logger.info("Creating new shop record", { shopId, shopDomain });
        shop = await config.prisma.shop.create({
          data: {
            shopId,
            shopDomain,
            accessToken,
            planType: "Free",
            isActive: true,
          },
        });
        Logger.info("Shop record created successfully", { shopId: shop.id });
      } else {
        Logger.info("Using existing shop record", { shopId: shop.id });
      }

      return shop;
    },
    "Shop record retrieval/creation",
    { shopId }
  );
};

// Clear existing data for a shop
export const clearShopData = async (
  config: DatabaseConfig,
  shopDbId: string
): Promise<void> => {
  await withDatabaseHealthCheck(
    config,
    async () => {
      Logger.info("Clearing existing data", { shopDbId });

      await config.prisma.orderData.deleteMany({
        where: { shopId: shopDbId },
      });
      await config.prisma.productData.deleteMany({
        where: { shopId: shopDbId },
      });
      await config.prisma.customerData.deleteMany({
        where: { shopId: shopDbId },
      });
    },
    "Data cleanup",
    { shopDbId }
  );
};

// Save orders to database with configurable behavior
export const saveOrders = async (
  config: DatabaseConfig,
  shopDbId: string,
  orders: DatabaseOrder[],
  isIncremental: boolean = false
): Promise<void> => {
  await withDatabaseHealthCheck(
    config,
    async () => {
      if (orders.length === 0) {
        Logger.info("No orders to save");
        return;
      }

      Logger.info("Processing orders for database", {
        ordersCount: orders.length,
        isIncremental,
      });

      const orderData = orders.map((order) => {
        // Transform lineItems from GraphQL structure to clean array
        let cleanLineItems;
        if (
          order.lineItems &&
          typeof order.lineItems === "object" &&
          "edges" in order.lineItems
        ) {
          // GraphQL structure: extract nodes from edges
          cleanLineItems = order.lineItems.edges.map((edge: any) => edge.node);
        } else if (Array.isArray(order.lineItems)) {
          // Already an array
          cleanLineItems = order.lineItems;
        } else {
          // Fallback
          cleanLineItems = order.lineItems || [];
        }

        return {
          shopId: shopDbId,
          orderId: order.orderId,
          customerId: order.customerId?.id || null,
          totalAmount: parseFloat(order.totalAmount.shopMoney.amount),
          orderDate: new Date(order.orderDate),
          orderStatus:
            order.displayFinancialStatus || order.fulfillmentStatus || null,
          currencyCode:
            order.currencyCode ||
            order.totalAmount.shopMoney.currencyCode ||
            null,
          lineItems: cleanLineItems,
        };
      });

      await config.prisma.orderData.createMany({
        data: orderData,
        skipDuplicates: isIncremental, // Skip duplicates only for incremental saves
      });
    },
    "Order data processing and saving",
    {
      ordersProcessed: orders.length,
      isIncremental,
    }
  );
};

// Save products to database with configurable behavior
export const saveProducts = async (
  config: DatabaseConfig,
  shopDbId: string,
  products: DatabaseProduct[],
  isIncremental: boolean = false
): Promise<void> => {
  await withDatabaseHealthCheck(
    config,
    async () => {
      if (products.length === 0) {
        Logger.info("No products to save");
        return;
      }

      Logger.info("Processing products for database", {
        productsCount: products.length,
        isIncremental,
      });

      if (isIncremental) {
        // For incremental saves, use upsert to update existing or create new
        for (const product of products) {
          await config.prisma.productData.upsert({
            where: {
              shopId_productId: {
                shopId: shopDbId,
                productId: product.id.toString(),
              },
            },
            update: {
              title: product.title,
              handle: product.handle,
              description: product.description || null,
              category: product.product_type || null,
              vendor: product.vendor || null,
              price: parseFloat(product.variants?.[0]?.price || "0"),
              compareAtPrice: product.variants?.[0]?.compareAtPrice
                ? parseFloat(product.variants[0].compareAtPrice)
                : null,
              inventory: product.variants?.[0]?.inventory_quantity || 0,
              tags: product.tags,
              imageUrl: product.image?.src || null,
              imageAlt: product.image?.alt || null,
              productCreatedAt: product.created_at
                ? new Date(product.created_at)
                : null,
              variants: product.variants as any,
              metafields: product.metafields as any,
              isActive: true,
              updatedAt: new Date(),
            },
            create: {
              shopId: shopDbId,
              productId: product.id.toString(),
              title: product.title,
              handle: product.handle,
              description: product.description || null,
              category: product.product_type || null,
              vendor: product.vendor || null,
              price: parseFloat(product.variants?.[0]?.price || "0"),
              compareAtPrice: product.variants?.[0]?.compareAtPrice
                ? parseFloat(product.variants[0].compareAtPrice)
                : null,
              inventory: product.variants?.[0]?.inventory_quantity || 0,
              tags: product.tags,
              imageUrl: product.image?.src || null,
              imageAlt: product.image?.alt || null,
              productCreatedAt: product.created_at
                ? new Date(product.created_at)
                : null,
              variants: product.variants as any,
              metafields: product.metafields as any,
              isActive: true,
            },
          });
        }
      } else {
        // For complete saves, use createMany for better performance
        const productData = products.map((product) => ({
          shopId: shopDbId,
          productId: product.id.toString(),
          title: product.title,
          handle: product.handle,
          description: product.description || null,
          category: product.product_type || null,
          vendor: product.vendor || null,
          price: parseFloat(product.variants?.[0]?.price || "0"),
          compareAtPrice: product.variants?.[0]?.compareAtPrice
            ? parseFloat(product.variants[0].compareAtPrice)
            : null,
          inventory: product.variants?.[0]?.inventory_quantity || 0,
          tags: product.tags,
          imageUrl: product.image?.src || null,
          imageAlt: product.image?.alt || null,
          productCreatedAt: product.created_at
            ? new Date(product.created_at)
            : null,
          variants: product.variants as any,
          metafields: product.metafields as any,
          isActive: true,
        }));

        await config.prisma.productData.createMany({
          data: productData,
        });
      }
    },
    "Product data processing and saving",
    {
      productsProcessed: products.length,
      isIncremental,
    }
  );
};

// Save customers to database
export const saveCustomers = async (
  config: DatabaseConfig,
  shopDbId: string,
  customers: DatabaseCustomer[],
  isIncremental: boolean = false
): Promise<void> => {
  await withDatabaseHealthCheck(
    config,
    async () => {
      if (customers.length === 0) {
        Logger.info("No customers to save");
        return;
      }

      Logger.info("Processing customers for database", {
        customersCount: customers.length,
        isIncremental,
      });

      for (const customer of customers) {
        await config.prisma.customerData.upsert({
          where: {
            shopId_customerId: {
              shopId: shopDbId,
              customerId: customer.id,
            },
          },
          update: {
            email: customer.email || null,
            firstName: customer.firstName || null,
            lastName: customer.lastName || null,
            createdAtShopify: customer.createdAt
              ? new Date(customer.createdAt)
              : null,
            lastOrderId: customer.lastOrder?.id || null,
            lastOrderDate: customer.lastOrder?.processedAt
              ? new Date(customer.lastOrder.processedAt)
              : null,
            tags: customer.tags || [],
            location: customer.addresses || [],
            metafields: customer.metafields || [],
            updatedAt: new Date(),
          },
          create: {
            shopId: shopDbId,
            customerId: customer.id,
            email: customer.email || null,
            firstName: customer.firstName || null,
            lastName: customer.lastName || null,
            createdAtShopify: customer.createdAt
              ? new Date(customer.createdAt)
              : null,
            lastOrderId: customer.lastOrder?.id || null,
            lastOrderDate: customer.lastOrder?.processedAt
              ? new Date(customer.lastOrder.processedAt)
              : null,
            tags: customer.tags || [],
            location: customer.addresses || [],
            metafields: customer.metafields || [],
          },
        });
      }
    },
    "Customer data processing and saving",
    {
      customersProcessed: customers.length,
      isIncremental,
    }
  );
};

// Update shop's last analysis timestamp
export const updateShopLastAnalysis = async (
  config: DatabaseConfig,
  shopDbId: string
): Promise<void> => {
  await withDatabaseHealthCheck(
    config,
    async () => {
      await config.prisma.shop.update({
        where: { id: shopDbId },
        data: { lastAnalysisAt: new Date() },
      });

      Logger.info("Updated shop last analysis timestamp", { shopDbId });
    },
    "Update shop last analysis timestamp",
    { shopDbId }
  );
};

// Get the latest timestamps from database for a shop in a single query
export const getLatestTimestamps = async (
  config: DatabaseConfig,
  shopDbId: string
): Promise<{
  latestOrderDate: Date | null;
  latestProductDate: Date | null;
}> => {
  return await withDatabaseHealthCheck(
    config,
    async () => {
      // Use a single query with multiple aggregations for better performance
      const result = await config.prisma.$queryRaw<
        Array<{
          latestOrderDate: Date | null;
          latestProductDate: Date | null;
        }>
      >`
        SELECT 
          MAX(o."orderDate") as "latestOrderDate",
          MAX(p."updatedAt") as "latestProductDate"
        FROM "OrderData" o
        FULL OUTER JOIN "ProductData" p ON o."shopId" = p."shopId"
        WHERE o."shopId" = ${shopDbId} OR p."shopId" = ${shopDbId}
      `;

      return {
        latestOrderDate: result[0]?.latestOrderDate || null,
        latestProductDate: result[0]?.latestProductDate || null,
      };
    },
    "Get latest timestamps (batched)",
    { shopDbId }
  );
};

// Get the latest order timestamp from database for a shop (legacy - use getLatestTimestamps instead)
export const getLatestOrderTimestamp = async (
  config: DatabaseConfig,
  shopDbId: string
): Promise<Date | null> => {
  const timestamps = await getLatestTimestamps(config, shopDbId);
  return timestamps.latestOrderDate;
};

// Get the latest product update timestamp from database for a shop (legacy - use getLatestTimestamps instead)
export const getLatestProductTimestamp = async (
  config: DatabaseConfig,
  shopDbId: string
): Promise<Date | null> => {
  const timestamps = await getLatestTimestamps(config, shopDbId);
  return timestamps.latestProductDate;
};

// Save heuristic decision for analysis scheduling
export const saveHeuristicDecision = async (
  config: DatabaseConfig,
  shopId: string,
  decision: {
    decision: string;
    reason: string;
    metadata?: any;
  }
): Promise<void> => {
  return await withDatabaseHealthCheck(
    config,
    async () => {
      await config.prisma.heuristicDecision.create({
        data: {
          shopId,
          decision: decision.decision,
          reason: decision.reason,
          metadata: decision.metadata || {},
        },
      });
    },
    "Save heuristic decision",
    { shopId, decision: decision.decision }
  );
};
