import express from "express";
import cors from "cors";
import helmet from "helmet";
import Queue from "bull";
import Redis from "ioredis";
import axios from "axios";
import dotenv from "dotenv";
import { prisma } from "shared/prisma";

// Load environment variables
dotenv.config({ path: "env/local.env" });

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
      "https://gateway-universities-relations-papua.trycloudflare.com";

    await axios.post(`${shopifyAppUrl}/api/analysis/update-status`, {
      jobId,
      status,
      progress,
      error,
    });
  } catch (error) {
    console.error(`Failed to update job status for ${jobId}:`, error);
  }
}

// Helper function to collect and save data from Shopify
async function collectAndSaveShopData(
  shopId: string,
  shopDomain: string,
  accessToken: string
) {
  try {
    // Calculate date 30 days ago
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const sinceDate = thirtyDaysAgo.toISOString().split("T")[0]; // Format: YYYY-MM-DD

    console.log(`📅 Collecting data since: ${sinceDate} (30 days ago)`);

    // Collect orders from last 30 days
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
      where: { shopId },
    });
    await prisma.productData.deleteMany({
      where: { shopId },
    });

    // Save products to database
    const productData = products.map((product: any) => ({
      shopId,
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
      shopId,
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
    console.error("Error collecting and saving data from Shopify:", error);
    throw error;
  }
}

// Helper function to collect incremental data from Shopify
async function collectIncrementalShopData(
  shopId: string,
  shopDomain: string,
  accessToken: string
) {
  try {
    // Get the last analysis timestamp from database
    const shop = await prisma.shop.findUnique({
      where: { shopId },
      select: { lastAnalysisAt: true },
    });

    let sinceDate: string;
    if (shop?.lastAnalysisAt) {
      // Use last analysis date as starting point
      sinceDate = shop.lastAnalysisAt.toISOString().split("T")[0];
      console.log(
        `📅 Collecting incremental data since: ${sinceDate} (last analysis)`
      );
    } else {
      // Fallback to 30 days ago if no last analysis
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      sinceDate = thirtyDaysAgo.toISOString().split("T")[0];
      console.log(
        `📅 Collecting incremental data since: ${sinceDate} (30 days ago - fallback)`
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
        shopId,
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
              shopId,
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
            shopId,
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
    console.error("Error collecting incremental data from Shopify:", error);
    throw error;
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

// Process analysis jobs
analysisQueue.process("analyze-shop", async (job) => {
  const { jobId, shopId, shopDomain, accessToken } = job.data;

  try {
    // Check if this is first run by looking for existing data
    const existingData = await prisma.orderData.findFirst({
      where: { shopId },
      select: { id: true },
    });

    // Check if there's a recent failed job for this shop
    const recentFailedJob = await prisma.analysisJob.findFirst({
      where: {
        shopId,
        status: "failed",
        createdAt: {
          gte: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
        },
      },
      orderBy: { createdAt: "desc" },
    });

    const isFirstRun = !existingData;
    const isRetryAfterFailure = !!recentFailedJob;

    console.log(
      `🔍 Processing analysis job: ${jobId} for shop: ${shopId} (${
        isFirstRun ? "first run" : "incremental"
      }${isRetryAfterFailure ? " - retry after failure" : ""})`
    );

    // Update job status to processing
    await updateJobStatus(jobId, "processing", 10);

    if (isFirstRun) {
      // First run: Collect all data from Shopify
      console.log(`📥 Collecting all data from Shopify for shop: ${shopId}`);
      const shopData = await collectAndSaveShopData(
        shopId,
        shopDomain,
        accessToken
      );
    } else if (isRetryAfterFailure) {
      // Retry after failure: Skip data collection, data already exists
      console.log(
        `📥 Skipping data collection for retry - data already exists for shop: ${shopId}`
      );
    } else {
      // Subsequent run: Collect only new data (incremental)
      console.log(
        `📥 Collecting incremental data from Shopify for shop: ${shopId}`
      );
      const shopData = await collectIncrementalShopData(
        shopId,
        shopDomain,
        accessToken
      );
    }

    await updateJobStatus(jobId, "processing", 50);

    // Queue ML processing job with shop ID (data is now in database)
    await mlProcessingQueue.add("process-ml-analysis", {
      jobId,
      shopId,
      shopDomain,
      accessToken,
    });

    console.log(`✅ Analysis job ${jobId} queued for ML processing`);
  } catch (error) {
    console.error(`❌ Error processing analysis job ${jobId}:`, error);
    await updateJobStatus(jobId, "failed", 0, error.message);
  }
});

// Process ML jobs
mlProcessingQueue.process("process-ml-analysis", async (job) => {
  const { jobId, shopId } = job.data;
  const shopifyAppUrl = process.env.SHOPIFY_APP_URL || "http://localhost:3000";

  try {
    console.log(`🤖 Processing ML job: ${jobId} for shop: ${shopId}`);

    await updateJobStatus(jobId, "processing", 70);

    // Call ML API with shop ID (data is in database)
    const mlApiUrl = process.env.RAILWAY_ML_API_URL || "http://localhost:8000";
    const mlResponse = await axios.post(
      `${mlApiUrl}/api/bundle-analysis/${shopId}`,
      {},
      {
        timeout: 300000, // 5 minutes timeout
        headers: { "Content-Type": "application/json" },
      }
    );

    const mlResult = mlResponse.data;

    await updateJobStatus(jobId, "processing", 90);

    // Call Shopify app to update results
    await axios.post(`${shopifyAppUrl}/api/analysis/complete`, {
      jobId,
      shopId,
      results: mlResult,
    });

    // Send push notification for successful completion
    try {
      await axios.post(`${shopifyAppUrl}/api/notifications/send`, {
        shopId,
        jobId,
        success: true,
      });
      console.log(`🔔 Notification sent for successful analysis: ${jobId}`);
    } catch (notificationError) {
      console.warn(
        `⚠️ Failed to send notification for job ${jobId}:`,
        notificationError.message
      );
    }

    await updateJobStatus(jobId, "completed", 100);

    console.log(`✅ ML job ${jobId} completed successfully`);
  } catch (error) {
    console.error(`❌ Error processing ML job ${jobId}:`, error);

    await updateJobStatus(jobId, "failed", 0, error.message);

    // Send push notification for failure
    try {
      await axios.post(`${shopifyAppUrl}/api/notifications/send`, {
        shopId,
        jobId,
        success: false,
      });
      console.log(`🔔 Notification sent for failed analysis: ${jobId}`);
    } catch (notificationError) {
      console.warn(
        `⚠️ Failed to send notification for job ${jobId}:`,
        notificationError.message
      );
    }
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
