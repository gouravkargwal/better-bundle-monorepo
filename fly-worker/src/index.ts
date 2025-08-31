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
import { ShopifyNotificationService } from "./utils/shopify-notification";
const envPath = path.join(__dirname, "../../local.env");
dotenv.config({ path: envPath });

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

// Initialize Redis client
const redis = new Redis(redisConfig);

// Initialize queues
const analysisQueue = new Queue("analysis-queue", { redis: redisConfig });
const mlProcessingQueue = new Queue("ml-processing-queue", {
  redis: redisConfig,
});

// Helper function to update job status in Shopify app
async function updateJobStatus(
  jobId: string,
  status: string,
  progress: number,
  error?: string
) {
  try {
    // Use the global environment variable
    const shopifyAppUrl =
      process.env.SHOPIFY_APP_URL ||
      "https://hottest-falls-adjusted-launched.trycloudflare.com";

    console.log(`📤 Updating job status: ${jobId} -> ${status} (${progress}%)`);

    await axios.post(
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

    console.log(`✅ Job status updated successfully: ${jobId} -> ${status}`);
  } catch (error) {
    console.error(`❌ Failed to update job status for ${jobId}:`, {
      message: error.message,
      code: error.code,
      hostname: error.hostname,
      url: error.config?.url,
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
  try {
    // Ensure shop exists in database
    let shop = await prisma.shop.findUnique({
      where: { shopId },
    });

    if (!shop) {
      console.log(`🏪 Creating shop record for: ${shopId}`);
      shop = await prisma.shop.create({
        data: {
          shopId,
          shopDomain,
          accessToken,
          planType: "Free",
          isActive: true,
        },
      });
    }

    // Use the shop's database ID for foreign key relationships
    const shopDbId = shop.id;
    console.log(
      `🏪 Using shop database ID: ${shopDbId} for data relationships`
    );

    // Calculate date 90 days ago
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 90);
    const sinceDate = thirtyDaysAgo.toISOString().split("T")[0]; // Format: YYYY-MM-DD

    console.log(`📅 Collecting data since: ${sinceDate} (90 days ago)`);

    // Collect orders from last 90 days
    const ordersResponse = await axios.get(
      `https://${shopDomain}/admin/api/2024-01/orders.json?status=any&created_at_min=${sinceDate}`,
      {
        headers: {
          "X-Shopify-Access-Token": accessToken,
          "Content-Type": "application/json",
        },
      }
    );

    // Collect products (all products, not limited by date)
    const productsResponse = await axios.get(
      `https://${shopDomain}/admin/api/2024-01/products.json`,
      {
        headers: {
          "X-Shopify-Access-Token": accessToken,
          "Content-Type": "application/json",
        },
      }
    );

    const orders = ordersResponse.data.orders || [];
    const products = productsResponse.data.products || [];

    console.log(
      `📊 Collected ${orders.length} orders and ${products.length} products`
    );

    // Clear existing data for this shop
    await prisma.orderData.deleteMany({
      where: { shopId: shopDbId },
    });
    await prisma.productData.deleteMany({
      where: { shopId: shopDbId },
    });

    // Save products to database
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

    // Save orders to database
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

    console.log(
      `💾 Saved ${products.length} products and ${orders.length} orders to database`
    );

    return {
      orders,
      products,
    };
  } catch (error) {
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
      // Fallback to 90 days ago if no last analysis
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 90);
      sinceDate = thirtyDaysAgo.toISOString().split("T")[0];
      console.log(
        `📅 Collecting incremental data since: ${sinceDate} (90 days ago - fallback)`
      );
    }

    // Collect only new orders since last analysis
    const ordersResponse = await axios.get(
      `https://${shopDomain}/admin/api/2024-01/orders.json?status=any&created_at_min=${sinceDate}`,
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

    const newOrders = ordersResponse.data.orders || [];
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
  res.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    service: "better-bundle-fly-worker",
  });
});

// Queue endpoint for receiving jobs from Shopify app
app.post("/api/queue", async (req, res) => {
  try {
    const { jobId, shopId, shopDomain, accessToken } = req.body;

    console.log(`📥 Received analysis job: ${jobId} for shop: ${shopId}`);

    // Add job to analysis queue
    await analysisQueue.add("analyze-shop", {
      jobId,
      shopId,
      shopDomain,
      accessToken,
      timestamp: new Date().toISOString(),
    });

    res.json({
      success: true,
      message: "Job queued successfully",
      jobId,
    });
  } catch (error) {
    console.error("❌ Error queuing job:", error);
    res.status(500).json({
      success: false,
      error: "Failed to queue job",
    });
  }
});

// Process ML jobs
mlProcessingQueue.process("process-ml-analysis", async (job) => {
  const { jobId, shopId } = job.data;

  // Get shop details from database
  let shop;
  try {
    shop = await prisma.shop.findUnique({
      where: { shopId },
      select: { shopDomain: true, accessToken: true },
    });

    if (!shop) {
      throw new Error(`Shop not found: ${shopId}`);
    }
  } catch (error) {
    console.error(`❌ Failed to get shop details for ${shopId}:`, error);
    throw error;
  }

  try {
    console.log(`🤖 Processing ML job: ${jobId} for shop: ${shopId}`);

    await updateJobStatus(jobId, "processing", 70);

    // Call ML API
    const mlApiUrl = process.env.ML_API_URL || "http://localhost:8000";
    const response = await axios.post(`${mlApiUrl}/analyze`, {
      shop_id: shopId,
    });

    if (response.data.success) {
      await updateJobStatus(jobId, "completed", 100);
      console.log(`✅ ML job completed: ${jobId}`);

      // Send success notification using Shopify App Events API
      await ShopifyNotificationService.sendAnalysisCompleteNotification(
        shop.shopDomain,
        shop.accessToken,
        jobId,
        true
      );
    } else {
      throw new Error(response.data.error || "ML API returned failure");
    }
  } catch (error) {
    console.error(`❌ ML job failed: ${jobId}`, error);
    await updateJobStatus(jobId, "failed", 0, error.message);

    // Send failure notification using Shopify App Events API
    await ShopifyNotificationService.sendAnalysisCompleteNotification(
      shop.shopDomain,
      shop.accessToken,
      jobId,
      false,
      error.message
    );

    throw error;
  }
});

// Process analysis jobs
analysisQueue.process("process-analysis", async (job) => {
  const { jobId, shopId } = job.data;

  // Get shop details from database
  let shop;
  try {
    shop = await prisma.shop.findUnique({
      where: { shopId },
      select: { shopDomain: true, accessToken: true },
    });

    if (!shop) {
      throw new Error(`Shop not found: ${shopId}`);
    }
  } catch (error) {
    console.error(`❌ Failed to get shop details for ${shopId}:`, error);
    throw error;
  }

  try {
    console.log(`📊 Processing analysis job: ${jobId} for shop: ${shopId}`);

    // Send analysis started notification using Shopify App Events API
    await ShopifyNotificationService.sendAnalysisStartedNotification(
      shop.shopDomain,
      shop.accessToken,
      jobId
    );

    await updateJobStatus(jobId, "processing", 30);

    // Collect shop data
    await collectAndSaveShopData(shopId, shop.shopDomain, shop.accessToken);

    await updateJobStatus(jobId, "processing", 60);

    // Add ML job to queue
    await mlProcessingQueue.add("process-ml-analysis", { jobId, shopId });

    console.log(`✅ Analysis job queued ML processing: ${jobId}`);
  } catch (error) {
    console.error(`❌ Analysis job failed: ${jobId}`, error);
    await updateJobStatus(jobId, "failed", 0, error.message);

    // Send failure notification using Shopify App Events API
    await ShopifyNotificationService.sendAnalysisCompleteNotification(
      shop.shopDomain,
      shop.accessToken,
      jobId,
      false,
      error.message
    );

    throw error;
  }
});

// Error handling for queues
analysisQueue.on("error", (error) => {
  console.error("❌ Analysis queue error:", error);
});

mlProcessingQueue.on("error", (error) => {
  console.error("❌ ML processing queue error:", error);
});

// Graceful shutdown
process.on("SIGTERM", async () => {
  console.log("🛑 Received SIGTERM, shutting down gracefully...");

  await analysisQueue.close();
  await mlProcessingQueue.close();
  await redis.disconnect();

  process.exit(0);
});

// Start server
const PORT = process.env.WORKER_PORT || 3001;
app.listen(PORT, () => {
  console.log(`🚀 Fly.io Worker running on port ${PORT}`);
  console.log(`📊 Analysis queue: ${analysisQueue.name}`);
  console.log(`🤖 ML processing queue: ${mlProcessingQueue.name}`);
});
