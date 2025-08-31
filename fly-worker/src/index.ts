import express from "express";
import cors from "cors";
import helmet from "helmet";
import Queue from "bull";
import Redis from "ioredis";
import axios from "axios";
import dotenv from "dotenv";
import { PrismaClient } from "@prisma/client";
import path from "path";
import { ErrorHandler } from "./utils/error-handler";
import { SendPulseEmailService } from "./utils/sendpulse-email";

// Enhanced logging utility
class Logger {
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

// Load environment variables from the global local.env file
const envPath = path.join(__dirname, "../../local.env");
Logger.info("Loading environment configuration", { envPath });
dotenv.config({ path: envPath });

// Log key environment variables for debugging
Logger.info("Environment configuration loaded", {
  DATABASE_URL: process.env.DATABASE_URL ? "✅ Set" : "❌ Missing",
  REDIS_HOST: process.env.REDIS_HOST || "localhost",
  REDIS_PORT: process.env.REDIS_PORT || "6379",
  SHOPIFY_APP_URL: process.env.SHOPIFY_APP_URL || "Not set",
  ML_API_URL: process.env.ML_API_URL || "Not set",
  WORKER_PORT: process.env.WORKER_PORT || "3001",
});

const prisma = new PrismaClient();
const app = express();

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Redis configuration
const redisConfig = {
  host: process.env.REDIS_HOST || "localhost",
  port: parseInt(process.env.REDIS_PORT || "6379"),
  password: process.env.REDIS_PASSWORD,
  tls: process.env.REDIS_TLS === "true" ? {} : undefined,
};

Logger.info("Initializing Redis connection", redisConfig);

// Initialize Redis client
const redis = new Redis(redisConfig);

redis.on("connect", () => {
  Logger.info("Redis connected successfully");
});

redis.on("error", (error) => {
  Logger.error("Redis connection error", error);
});

// Initialize queues
const analysisQueue = new Queue("analysis-queue", { redis: redisConfig });
const mlProcessingQueue = new Queue("ml-processing-queue", {
  redis: redisConfig,
});

Logger.info("Queue initialization completed", {
  analysisQueue: analysisQueue.name,
  mlProcessingQueue: mlProcessingQueue.name,
});

// Helper function to update job status in Shopify app
async function updateJobStatus(
  jobId: string,
  status: string,
  progress: number,
  error?: string
) {
  const startTime = Date.now();
  try {
    // Use the global environment variable
    const shopifyAppUrl =
      process.env.SHOPIFY_APP_URL ||
      "https://hottest-falls-adjusted-launched.trycloudflare.com";

    Logger.info("Updating job status", {
      jobId,
      status,
      progress,
      hasError: !!error,
      shopifyAppUrl,
    });

    const response = await axios.post(
      `${shopifyAppUrl}/api/analysis/update-status`,
      {
        jobId,
        status,
        progress,
        error,
      },
      {
        timeout: 10000, // 10 second timeout
      }
    );

    const duration = Date.now() - startTime;
    Logger.performance("Job status update", duration, {
      jobId,
      status,
      progress,
      responseStatus: response.status,
    });

    Logger.info("Job status updated successfully", {
      jobId,
      status,
      progress,
      responseStatus: response.status,
    });
  } catch (error) {
    const duration = Date.now() - startTime;
    Logger.error("Failed to update job status", {
      jobId,
      status,
      progress,
      duration,
      error,
    });
    throw error; // Re-throw so the caller can handle it
  }
}

// Helper function to collect and save data from Shopify
async function collectAndSaveShopData(
  shopId: string,
  shopDomain: string,
  accessToken: string
) {
  const startTime = Date.now();
  Logger.info("Starting data collection", {
    shopId,
    shopDomain,
    hasAccessToken: !!accessToken,
  });

  try {
    // Ensure shop exists in database
    let shop = await prisma.shop.findUnique({
      where: { shopId },
    });

    if (!shop) {
      Logger.info("Creating new shop record", { shopId, shopDomain });
      shop = await prisma.shop.create({
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

    // Use the shop's database ID for foreign key relationships
    const shopDbId = shop.id;
    Logger.info("Shop database ID resolved", { shopDbId });

    // Calculate date 60 days ago
    const sixtyDaysAgo = new Date();
    sixtyDaysAgo.setDate(sixtyDaysAgo.getDate() - 60);
    const sinceDate = sixtyDaysAgo.toISOString().split("T")[0]; // Format: YYYY-MM-DD

    Logger.info("Data collection parameters", {
      sinceDate,
      daysBack: 60,
      shopDomain,
    });

    // Collect orders from last 50 days using GraphQL
    Logger.info("Fetching orders from Shopify GraphQL API", {
      shopDomain,
      sinceDate,
    });

    const ordersStartTime = Date.now();

    // GraphQL query for orders with pagination
    const graphqlQuery = `
      query getOrders($query: String!, $after: String) {
        orders(first: 250, query: $query, after: $after) {
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              id
              name
              createdAt
              totalPriceSet {
                shopMoney {
                  amount
                }
              }
              customer {
                id
              }
              lineItems(first: 50) {
                edges {
                  node {
                    product {
                      id
                    }
                    variant {
                      id
                      price
                    }
                    quantity
                    title
                  }
                }
              }
            }
          }
        }
      }
    `;

    // Collect all orders using pagination
    let allOrders: any[] = [];
    let hasNextPage = true;
    let cursor: string | null = null;

    while (hasNextPage) {
      const ordersResponse = await axios.post(
        `https://${shopDomain}/admin/api/2024-01/graphql.json`,
        {
          query: graphqlQuery,
          variables: {
            query: `created_at:>='${sinceDate}'`,
            after: cursor,
          },
        },
        {
          headers: {
            "X-Shopify-Access-Token": accessToken,
            "Content-Type": "application/json",
          },
          timeout: 30000, // 30 second timeout for orders
        }
      );

      const responseData = ordersResponse.data.data?.orders;
      const edges = responseData?.edges || [];

      allOrders = allOrders.concat(edges);

      hasNextPage = responseData?.pageInfo?.hasNextPage || false;
      cursor = responseData?.pageInfo?.endCursor || null;

      Logger.info("Orders pagination progress", {
        shopDomain,
        ordersCollected: allOrders.length,
        hasNextPage,
        cursor: cursor ? cursor.substring(0, 20) + "..." : null,
      });
    }

    const ordersDuration = Date.now() - ordersStartTime;
    Logger.performance("Orders GraphQL API call", ordersDuration, {
      shopDomain,
      ordersCount: allOrders.length,
    });

    // Collect products (all products, not limited by date)
    Logger.info("Fetching products from Shopify API", { shopDomain });

    const productsStartTime = Date.now();
    const productsResponse = await axios.get(
      `https://${shopDomain}/admin/api/2024-01/products.json`,
      {
        headers: {
          "X-Shopify-Access-Token": accessToken,
          "Content-Type": "application/json",
        },
        timeout: 30000, // 30 second timeout for products
      }
    );
    const productsDuration = Date.now() - productsStartTime;
    Logger.performance("Products API call", productsDuration, {
      shopDomain,
      productsCount: productsResponse.data.products?.length || 0,
    });

    // Transform GraphQL orders response to match expected format
    const orders = (ordersResponse.data.data?.orders?.edges || []).map(
      (edge: any) => {
        const order = edge.node;
        return {
          id: order.id,
          order_number: order.name,
          total_price: order.totalPriceSet?.shopMoney?.amount || "0",
          created_at: order.createdAt,
          customer: order.customer ? { id: order.customer.id } : null,
          line_items:
            order.lineItems?.edges?.map((lineEdge: any) => {
              const lineItem = lineEdge.node;
              return {
                product_id: lineItem.product?.id,
                variant_id: lineItem.variant?.id,
                title: lineItem.title,
                quantity: lineItem.quantity,
                price: lineItem.variant?.price || "0",
              };
            }) || [],
        };
      }
    );

    const products = productsResponse.data.products || [];

    Logger.info("Data collection completed", {
      ordersCount: orders.length,
      productsCount: products.length,
      totalDuration: Date.now() - startTime,
    });

    // Clear existing data for this shop
    Logger.info("Clearing existing data", { shopDbId });
    const clearStartTime = Date.now();

    await prisma.orderData.deleteMany({
      where: { shopId: shopDbId },
    });
    await prisma.productData.deleteMany({
      where: { shopId: shopDbId },
    });

    const clearDuration = Date.now() - clearStartTime;
    Logger.performance("Data cleanup", clearDuration, { shopDbId });

    // Save products to database
    Logger.info("Processing products for database", {
      productsCount: products.length,
    });

    const productProcessingStartTime = Date.now();
    const productData = products.map((product: any) => ({
      shopId: shopDbId,
      productId: product.id.toString(),
      title: product.title,
      handle: product.handle,
      category: product.product_type || null,
      price: parseFloat(product.variants?.[0]?.price || "0"),
      inventory: product.variants?.[0]?.inventory_quantity || 0,
      tags: product.tags
        ? product.tags.split(", ").filter((tag: string) => tag.trim())
        : [],
      imageUrl: product.image?.src || null,
      imageAlt: product.image?.alt || null,
      isActive: true,
    }));

    await prisma.productData.createMany({
      data: productData,
    });

    const productProcessingDuration = Date.now() - productProcessingStartTime;
    Logger.performance(
      "Product data processing and saving",
      productProcessingDuration,
      {
        productsProcessed: products.length,
      }
    );

    // Save orders to database
    Logger.info("Processing orders for database", {
      ordersCount: orders.length,
    });

    const orderProcessingStartTime = Date.now();
    const orderData = orders.map((order: any) => ({
      shopId: shopDbId,
      orderId: order.id.toString(),
      customerId: order.customer?.id?.toString() || null,
      totalAmount: parseFloat(order.total_price || "0"),
      orderDate: new Date(order.created_at),
      lineItems:
        order.line_items?.map((item: any) => ({
          product_id: item.product_id?.toString(),
          variant_id: item.variant_id?.toString(),
          title: item.title,
          quantity: item.quantity,
          price: parseFloat(item.price || "0"),
        })) || [],
    }));

    await prisma.orderData.createMany({
      data: orderData,
    });

    const orderProcessingDuration = Date.now() - orderProcessingStartTime;
    Logger.performance(
      "Order data processing and saving",
      orderProcessingDuration,
      {
        ordersProcessed: orders.length,
      }
    );

    const totalDuration = Date.now() - startTime;
    Logger.performance("Complete data collection and saving", totalDuration, {
      shopId,
      shopDomain,
      productsSaved: products.length,
      ordersSaved: orders.length,
    });

    Logger.info("Data collection and saving completed successfully", {
      shopId,
      shopDomain,
      productsSaved: products.length,
      ordersSaved: orders.length,
      totalDuration,
    });

    return {
      orders,
      products,
    };
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("Data collection failed", {
      shopId,
      shopDomain,
      totalDuration,
      error,
    });

    // Check for specific API permission errors
    if (error?.response?.status === 403) {
      Logger.error("Shopify API permission denied", {
        shopId,
        shopDomain,
        status: error.response.status,
        statusText: error.response.statusText,
        url: error.config?.url,
        scopes: "Check if app has read_orders scope",
      });

      throw new Error(
        "Shopify API access denied. Please ensure the app has the required permissions (read_orders scope) and the access token is valid."
      );
    }

    // Check for authentication errors (401)
    if (error?.response?.status === 401) {
      Logger.error("Shopify API authentication failed", {
        shopId,
        shopDomain,
        status: error.response.status,
        statusText: error.response.statusText,
        url: error.config?.url,
        message: "Access token may be expired or invalid",
      });

      throw new Error(
        "Shopify API authentication failed. The access token may be expired or invalid. Please reinstall the app to refresh the token."
      );
    }

    const userFriendlyError = ErrorHandler.toUserFriendlyError(error, {
      operation: "collectAndSaveShopData",
      shopId,
    });
    throw new Error(userFriendlyError);
  }
}

// Helper function to collect incremental data from Shopify
async function collectIncrementalShopData(
  shopId: string,
  shopDomain: string,
  accessToken: string
) {
  try {
    // Ensure shop exists in database
    let shop = await prisma.shop.findUnique({
      where: { shopId },
      select: { id: true, lastAnalysisAt: true },
    });

    if (!shop) {
      console.log(`🏪 Creating shop record for: ${shopId}`);
      const newShop = await prisma.shop.create({
        data: {
          shopId,
          shopDomain,
          accessToken,
          planType: "Free",
          isActive: true,
        },
      });
      shop = await prisma.shop.findUnique({
        where: { shopId },
        select: { id: true, lastAnalysisAt: true },
      });
    }

    if (!shop) {
      throw new Error("Failed to create or find shop record");
    }

    // Use the shop's database ID for foreign key relationships
    const shopDbId = shop.id;
    console.log(
      `🏪 Using shop database ID: ${shopDbId} for incremental data relationships`
    );

    let sinceDate: string;
    if (shop?.lastAnalysisAt) {
      // Use last analysis date as starting point
      sinceDate = shop.lastAnalysisAt.toISOString().split("T")[0];
      console.log(
        `📅 Collecting incremental data since: ${sinceDate} (last analysis)`
      );
    } else {
      // Fallback to 50 days ago if no last analysis
      const fiftyDaysAgo = new Date();
      fiftyDaysAgo.setDate(fiftyDaysAgo.getDate() - 50);
      sinceDate = fiftyDaysAgo.toISOString().split("T")[0];
      console.log(
        `📅 Collecting incremental data since: ${sinceDate} (50 days ago - fallback)`
      );
    }

    // Collect only new orders since last analysis using GraphQL
    const graphqlQuery = `
      query getOrders($query: String!) {
        orders(first: 250, query: $query) {
          edges {
            node {
              id
              name
              createdAt
              totalPriceSet {
                shopMoney {
                  amount
                }
              }
              customer {
                id
              }
              lineItems(first: 50) {
                edges {
                  node {
                    product {
                      id
                    }
                    variant {
                      id
                      price
                    }
                    quantity
                    title
                  }
                }
              }
            }
          }
        }
      }
    `;

    const ordersResponse = await axios.post(
      `https://${shopDomain}/admin/api/2024-01/graphql.json`,
      {
        query: graphqlQuery,
        variables: {
          query: `created_at:>='${sinceDate}'`,
        },
      },
      {
        headers: {
          "X-Shopify-Access-Token": accessToken,
          "Content-Type": "application/json",
        },
      }
    );

    // Collect only new/updated products since last analysis
    const productsResponse = await axios.get(
      `https://${shopDomain}/admin/api/2024-01/products.json?updated_at_min=${sinceDate}`,
      {
        headers: {
          "X-Shopify-Access-Token": accessToken,
          "Content-Type": "application/json",
        },
      }
    );

    // Transform GraphQL orders response for incremental analysis
    const newOrders = (ordersResponse.data.data?.orders?.edges || []).map(
      (edge: any) => {
        const order = edge.node;
        return {
          id: order.id,
          order_number: order.name,
          total_price: order.totalPriceSet?.shopMoney?.amount || "0",
          created_at: order.createdAt,
          customer: order.customer ? { id: order.customer.id } : null,
          line_items:
            order.lineItems?.edges?.map((lineEdge: any) => {
              const lineItem = lineEdge.node;
              return {
                product_id: lineItem.product?.id,
                variant_id: lineItem.variant?.id,
                title: lineItem.title,
                quantity: lineItem.quantity,
                price: lineItem.variant?.price || "0",
              };
            }) || [],
        };
      }
    );

    const updatedProducts = productsResponse.data.products || [];

    console.log(
      `📊 Collected ${newOrders.length} new orders and ${updatedProducts.length} updated products`
    );

    // Save new orders to database (don't clear existing ones)
    if (newOrders.length > 0) {
      const orderData = newOrders.map((order: any) => ({
        shopId: shopDbId,
        orderId: order.id.toString(),
        customerId: order.customer?.id?.toString() || null,
        totalAmount: parseFloat(order.total_price || "0"),
        orderDate: new Date(order.created_at),
        lineItems:
          order.line_items?.map((item: any) => ({
            product_id: item.product_id?.toString(),
            variant_id: item.variant_id?.toString(),
            title: item.title,
            quantity: item.quantity,
            price: parseFloat(item.price || "0"),
          })) || [],
      }));

      await prisma.orderData.createMany({
        data: orderData,
        skipDuplicates: true, // Skip if order already exists
      });
    }

    // Update existing products or add new ones
    if (updatedProducts.length > 0) {
      for (const product of updatedProducts) {
        await prisma.productData.upsert({
          where: {
            shopId_productId: {
              shopId: shopDbId,
              productId: product.id.toString(),
            },
          },
          update: {
            title: product.title,
            handle: product.handle,
            category: product.product_type || null,
            price: parseFloat(product.variants?.[0]?.price || "0"),
            inventory: product.variants?.[0]?.inventory_quantity || 0,
            tags: product.tags
              ? product.tags.split(", ").filter((tag: string) => tag.trim())
              : [],
            imageUrl: product.image?.src || null,
            imageAlt: product.image?.alt || null,
            isActive: true,
            updatedAt: new Date(),
          },
          create: {
            shopId: shopDbId,
            productId: product.id.toString(),
            title: product.title,
            handle: product.handle,
            category: product.product_type || null,
            price: parseFloat(product.variants?.[0]?.price || "0"),
            inventory: product.variants?.[0]?.inventory_quantity || 0,
            tags: product.tags
              ? product.tags.split(", ").filter((tag: string) => tag.trim())
              : [],
            imageUrl: product.image?.src || null,
            imageAlt: product.image?.alt || null,
            isActive: true,
          },
        });
      }
    }

    console.log(
      `💾 Incrementally saved ${newOrders.length} new orders and updated ${updatedProducts.length} products`
    );

    return {
      orders: newOrders,
      products: updatedProducts,
    };
  } catch (error) {
    const userFriendlyError = ErrorHandler.toUserFriendlyError(error, {
      operation: "collectIncrementalShopData",
      shopId,
    });
    throw new Error(userFriendlyError);
  }
}

// Health check endpoint
app.get("/health", (req, res) => {
  Logger.info("Health check requested", {
    timestamp: new Date().toISOString(),
    service: "better-bundle-fly-worker",
  });

  res.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    service: "better-bundle-fly-worker",
  });
});

// Queue endpoint for receiving jobs from Shopify app
app.post("/api/queue", async (req, res) => {
  const startTime = Date.now();
  Logger.info("Received queue job request", {
    body: req.body,
    headers: req.headers,
  });

  try {
    const { jobId, shopId, shopDomain, accessToken } = req.body;

    Logger.info("Processing queue job", {
      jobId,
      shopId,
      shopDomain,
      hasAccessToken: !!accessToken,
    });

    // Add job to analysis queue
    const queueStartTime = Date.now();
    await analysisQueue.add("process-analysis", {
      jobId,
      shopId,
      shopDomain,
      accessToken,
      timestamp: new Date().toISOString(),
    });
    const queueDuration = Date.now() - queueStartTime;

    Logger.performance("Job queuing", queueDuration, {
      jobId,
      shopId,
      queueName: analysisQueue.name,
    });

    const totalDuration = Date.now() - startTime;
    Logger.info("Job queued successfully", {
      jobId,
      shopId,
      totalDuration,
    });

    res.json({
      success: true,
      message: "Job queued successfully",
      jobId,
    });
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("Failed to queue job", {
      totalDuration,
      error,
    });

    res.status(500).json({
      success: false,
      error: "Failed to queue job",
    });
  }
});

// Process ML jobs
mlProcessingQueue.process("process-ml-analysis", async (job) => {
  const { jobId, shopId, shopDomain } = job.data;
  const startTime = Date.now();

  Logger.info("Starting ML job processing", {
    jobId,
    shopId,
    shopDomain,
    jobData: job.data,
  });

  // Get shop details from database
  let shop;
  try {
    Logger.info("Fetching shop details for ML processing", { shopDomain });

    const shopFetchStartTime = Date.now();
    shop = await prisma.shop.findUnique({
      where: { shopDomain },
      select: { shopDomain: true, accessToken: true },
    });
    const shopFetchDuration = Date.now() - shopFetchStartTime;

    Logger.performance("Shop details fetch", shopFetchDuration, { shopDomain });

    if (!shop) {
      throw new Error(`Shop not found: ${shopDomain}`);
    }

    Logger.info("Shop details retrieved successfully", {
      shopDomain: shop.shopDomain,
      hasAccessToken: !!shop.accessToken,
    });
  } catch (error) {
    Logger.error("Failed to get shop details for ML processing", {
      shopDomain,
      error,
    });
    throw error;
  }

  try {
    Logger.info("Processing ML analysis", {
      jobId,
      shopId,
      shopDomain,
    });

    await updateJobStatus(jobId, "processing", 70);

    // Call ML API
    const mlApiUrl = process.env.ML_API_URL || "http://localhost:8000";
    Logger.info("Calling ML API", {
      jobId,
      mlApiUrl,
      shopId,
    });

    const mlApiStartTime = Date.now();
    const response = await axios.post(
      `${mlApiUrl}/analyze`,
      {
        shop_id: shopId,
      },
      {
        timeout: 120000, // 2 minute timeout for ML processing
      }
    );
    const mlApiDuration = Date.now() - mlApiStartTime;

    Logger.performance("ML API call", mlApiDuration, {
      jobId,
      shopId,
      responseStatus: response.status,
      responseSuccess: response.data.success,
    });

    if (response.data.success) {
      await updateJobStatus(jobId, "completed", 100);
      Logger.info("ML job completed successfully", {
        jobId,
        shopId,
        totalDuration: Date.now() - startTime,
      });

      // Send success email notification
      try {
        Logger.info("Sending success email notification", { jobId });

        const emailStartTime = Date.now();
        const emailService = SendPulseEmailService.getInstance();
        await emailService.sendAnalysisCompleteNotification(
          "admin@example.com", // TODO: Get actual user email from shop data
          shop.shopDomain,
          true
        );
        const emailDuration = Date.now() - emailStartTime;

        Logger.performance("Success email sending", emailDuration, { jobId });
        Logger.info("Success email sent successfully", { jobId });
      } catch (emailError) {
        Logger.warn("Failed to send success email", {
          jobId,
          error: emailError.message,
        });
      }
    } else {
      throw new Error(response.data.error || "ML API returned failure");
    }
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("ML job failed", {
      jobId,
      shopId,
      totalDuration,
      error,
    });

    await updateJobStatus(jobId, "failed", 0, error.message);

    // Send failure email notification
    try {
      Logger.info("Sending failure email notification", { jobId });

      const emailStartTime = Date.now();
      const emailService = SendPulseEmailService.getInstance();
      await emailService.sendAnalysisCompleteNotification(
        "admin@example.com", // TODO: Get actual user email from shop data
        shop.shopDomain,
        false,
        error.message
      );
      const emailDuration = Date.now() - emailStartTime;

      Logger.performance("Failure email sending", emailDuration, { jobId });
      Logger.info("Failure email sent successfully", { jobId });
    } catch (emailError) {
      Logger.warn("Failed to send failure email", {
        jobId,
        error: emailError.message,
      });
    }

    throw error;
  }
});

// Process analysis jobs
analysisQueue.process("process-analysis", async (job) => {
  const { jobId, shopId } = job.data;
  const startTime = Date.now();

  Logger.info("Starting analysis job processing", {
    jobId,
    shopId,
    jobData: job.data,
  });

  // Get shop details from database
  let shop;
  try {
    Logger.info("Fetching shop details for analysis", { shopId });

    const shopFetchStartTime = Date.now();
    shop = await prisma.shop.findUnique({
      where: { shopId },
      select: { shopDomain: true, accessToken: true },
    });
    const shopFetchDuration = Date.now() - shopFetchStartTime;

    Logger.performance("Shop details fetch for analysis", shopFetchDuration, {
      shopId,
    });

    if (!shop) {
      throw new Error(`Shop not found: ${shopId}`);
    }

    Logger.info("Shop details retrieved for analysis", {
      shopDomain: shop.shopDomain,
      hasAccessToken: !!shop.accessToken,
    });
  } catch (error) {
    Logger.error("Failed to get shop details for analysis", {
      shopId,
      error,
    });
    throw error;
  }

  try {
    Logger.info("Processing analysis job", {
      jobId,
      shopId,
      shopDomain: shop.shopDomain,
    });

    // Send analysis started email notification
    try {
      Logger.info("Sending analysis started email notification", { jobId });

      const emailStartTime = Date.now();
      const emailService = SendPulseEmailService.getInstance();
      await emailService.sendAnalysisStartedNotification(
        "admin@example.com", // TODO: Get actual user email from shop data
        shop.shopDomain
      );
      const emailDuration = Date.now() - emailStartTime;

      Logger.performance("Analysis started email sending", emailDuration, {
        jobId,
      });
      Logger.info("Analysis started email sent successfully", { jobId });
    } catch (emailError) {
      Logger.warn("Failed to send analysis started email", {
        jobId,
        error: emailError.message,
      });
    }

    Logger.info("Updating job status to processing (30%)", { jobId });
    await updateJobStatus(jobId, "processing", 30);

    Logger.info("Starting data collection", {
      jobId,
      shopDomain: shop.shopDomain,
    });

    // Collect shop data
    const dataCollectionStartTime = Date.now();
    await collectAndSaveShopData(shopId, shop.shopDomain, shop.accessToken);
    const dataCollectionDuration = Date.now() - dataCollectionStartTime;

    Logger.performance("Data collection", dataCollectionDuration, {
      jobId,
      shopDomain: shop.shopDomain,
    });

    Logger.info("Data collection completed", { jobId });

    Logger.info("Updating job status to processing (60%)", { jobId });
    await updateJobStatus(jobId, "processing", 60);

    Logger.info("Adding ML job to queue", { jobId });

    // Add ML job to queue
    const mlQueueStartTime = Date.now();
    await mlProcessingQueue.add("process-ml-analysis", { jobId, shopId });
    const mlQueueDuration = Date.now() - mlQueueStartTime;

    Logger.performance("ML job queuing", mlQueueDuration, {
      jobId,
      shopId,
      queueName: mlProcessingQueue.name,
    });

    Logger.info("Analysis job completed, ML job queued", {
      jobId,
      totalDuration: Date.now() - startTime,
    });
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("Analysis job failed", {
      jobId,
      shopId,
      totalDuration,
      error,
    });

    await updateJobStatus(jobId, "failed", 0, error.message);
    throw error;
  }
});

// Error handling for queues
analysisQueue.on("error", (error) => {
  Logger.error("Analysis queue error", error);
});

mlProcessingQueue.on("error", (error) => {
  Logger.error("ML processing queue error", error);
});

// Queue event listeners for better monitoring
analysisQueue.on("waiting", (jobId) => {
  Logger.info("Analysis job waiting", {
    jobId,
  });
});

analysisQueue.on("active", (job) => {
  Logger.info("Analysis job started", {
    jobId: job.id,
    jobData: job.data,
  });
});

analysisQueue.on("completed", (job) => {
  Logger.info("Analysis job completed", {
    jobId: job.id,
    jobData: job.data,
  });
});

analysisQueue.on("failed", (job, error) => {
  Logger.error("Analysis job failed", {
    jobId: job.id,
    jobData: job.data,
    error,
  });
});

mlProcessingQueue.on("waiting", (jobId) => {
  Logger.info("ML job waiting", {
    jobId,
  });
});

mlProcessingQueue.on("active", (job) => {
  Logger.info("ML job started", {
    jobId: job.id,
    jobData: job.data,
  });
});

mlProcessingQueue.on("completed", (job) => {
  Logger.info("ML job completed", {
    jobId: job.id,
    jobData: job.data,
  });
});

mlProcessingQueue.on("failed", (job, error) => {
  Logger.error("ML job failed", {
    jobId: job.id,
    jobData: job.data,
    error,
  });
});

// Graceful shutdown
process.on("SIGTERM", async () => {
  Logger.info("Received SIGTERM, starting graceful shutdown");

  try {
    Logger.info("Closing analysis queue");
    await analysisQueue.close();

    Logger.info("Closing ML processing queue");
    await mlProcessingQueue.close();

    Logger.info("Disconnecting Redis");
    await redis.disconnect();

    Logger.info("Graceful shutdown completed");
    process.exit(0);
  } catch (error) {
    Logger.error("Error during graceful shutdown", error);
    process.exit(1);
  }
});

process.on("SIGINT", async () => {
  Logger.info("Received SIGINT, starting graceful shutdown");

  try {
    Logger.info("Closing analysis queue");
    await analysisQueue.close();

    Logger.info("Closing ML processing queue");
    await mlProcessingQueue.close();

    Logger.info("Disconnecting Redis");
    await redis.disconnect();

    Logger.info("Graceful shutdown completed");
    process.exit(0);
  } catch (error) {
    Logger.error("Error during graceful shutdown", error);
    process.exit(1);
  }
});

// Start server
const PORT = process.env.WORKER_PORT || 3001;
app.listen(PORT, () => {
  Logger.info("Fly.io Worker started successfully", {
    port: PORT,
    analysisQueue: analysisQueue.name,
    mlProcessingQueue: mlProcessingQueue.name,
    environment: process.env.NODE_ENV || "development",
    timestamp: new Date().toISOString(),
  });
});
