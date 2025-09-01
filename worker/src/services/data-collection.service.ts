import { Logger } from "../utils/logger";
import {
  createShopifyAxiosInstance,
  fetchOrders,
  fetchProducts,
  fetchCustomers,
  ShopifyApiConfig,
  DatabaseOrder,
  DatabaseProduct,
  DatabaseCustomer,
} from "./shopify-api.service";
import {
  getOrCreateShop,
  clearShopData,
  saveOrders,
  saveProducts,
  saveCustomers,
  updateShopLastAnalysis,
  getLatestTimestamps,
  DatabaseConfig,
} from "./database.service";

export interface DataCollectionConfig {
  database: DatabaseConfig;
  shopifyApi: ShopifyApiConfig;
  daysBack?: number;
}

export interface DataCollectionResult {
  orders: DatabaseOrder[];
  products: DatabaseProduct[];
  customers: DatabaseCustomer[];
  shopDbId: string;
}

// Configuration constants
export const DATA_COLLECTION_CONFIG = {
  // Maximum days to fetch for initial data collection (2 months = ~60 days)
  MAX_INITIAL_DAYS: parseInt(process.env.MAX_INITIAL_DAYS || "60"),
  // Maximum days to fetch for incremental data collection
  MAX_INCREMENTAL_DAYS: parseInt(process.env.MAX_INCREMENTAL_DAYS || "30"),
  // Fallback days if no last analysis timestamp exists
  FALLBACK_DAYS: parseInt(process.env.FALLBACK_DAYS || "30"),
} as const;

// Calculate date for data collection using Shopify's timestamp format
export const calculateSinceDate = (
  daysBack: number = DATA_COLLECTION_CONFIG.MAX_INITIAL_DAYS
): string => {
  const date = new Date();
  date.setDate(date.getDate() - daysBack);
  return date.toISOString(); // Use full ISO timestamp for Shopify API
};

// Collect and save complete shop data
export const collectAndSaveShopData = async (
  config: DataCollectionConfig
): Promise<DataCollectionResult> => {
  const startTime = Date.now();
  const { shopId, shopDomain, accessToken } = config.shopifyApi;

  Logger.info("Starting complete data collection", {
    shopId,
    shopDomain,
    hasAccessToken: !!accessToken,
    daysBack: config.daysBack || 60,
  });

  try {
    // Get or create shop record
    const shop = await getOrCreateShop(
      config.database,
      shopId,
      shopDomain,
      accessToken
    );

    const shopDbId = shop.id;
    Logger.info("Shop database ID resolved", { shopDbId });

    // For complete data collection, get data from the configured time period
    const sinceDate = calculateSinceDate(
      config.daysBack || DATA_COLLECTION_CONFIG.MAX_INITIAL_DAYS
    );
    Logger.info(
      "Complete data collection - fetching data from configured period",
      {
        shopDomain,
        sinceDate,
        daysBack: config.daysBack || DATA_COLLECTION_CONFIG.MAX_INITIAL_DAYS,
      }
    );

    // Create Shopify API instance
    const shopifyApi = createShopifyAxiosInstance(config.shopifyApi);

    // Collect orders and products in parallel for better performance
    Logger.info(
      "Fetching orders and products from Shopify GraphQL API in parallel",
      {
        shopDomain,
        sinceDate,
      }
    );

    const parallelStartTime = Date.now();

    // Execute both API calls simultaneously
    const [orders, products] = await Promise.all([
      fetchOrders(shopifyApi, sinceDate),
      fetchProducts(shopifyApi),
    ]);
    const customers = await fetchCustomers(shopifyApi, sinceDate);

    const parallelDuration = Date.now() - parallelStartTime;

    Logger.performance("Parallel data collection", parallelDuration, {
      shopDomain,
      ordersCount: orders.length,
      productsCount: products.length,
      customersCount: customers.length,
    });

    Logger.info("Data collection completed", {
      ordersCount: orders.length,
      productsCount: products.length,
      customersCount: customers.length,
      totalDuration: Date.now() - startTime,
    });

    // Clear existing data
    await clearShopData(config.database, shopDbId);

    // Save data to database in parallel - no transformation needed
    await Promise.all([
      saveProducts(config.database, shopDbId, products),
      saveOrders(config.database, shopDbId, orders),
      saveCustomers(config.database, shopDbId, customers),
    ]);

    // Update shop's last analysis timestamp
    await updateShopLastAnalysis(config.database, shopDbId);

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
      customers,
      shopDbId,
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

    throw error;
  }
};

// Collect and save incremental shop data
export const collectIncrementalShopData = async (
  config: DataCollectionConfig
): Promise<DataCollectionResult> => {
  const startTime = Date.now();
  const { shopId, shopDomain, accessToken } = config.shopifyApi;

  Logger.info("Starting incremental data collection", {
    shopId,
    shopDomain,
    hasAccessToken: !!accessToken,
  });

  try {
    // Get or create shop record
    const shop = await getOrCreateShop(
      config.database,
      shopId,
      shopDomain,
      accessToken
    );

    const shopDbId = shop.id;
    Logger.info("Shop database ID resolved", { shopDbId });

    // Determine since date for incremental collection
    let sinceDate: string;
    let collectionType: string;

    // Get the latest timestamps from our database in a single query
    const {
      latestOrderDate: latestOrderTimestamp,
      latestProductDate: latestProductTimestamp,
    } = await getLatestTimestamps(config.database, shopDbId);

    if (shop?.lastAnalysisAt) {
      // Use last analysis timestamp as starting point
      sinceDate = shop.lastAnalysisAt.toISOString();
      collectionType = "incremental_since_last_analysis";
      Logger.info("Collecting incremental data since last analysis", {
        sinceDate,
        lastAnalysisAt: shop.lastAnalysisAt,
        latestOrderTimestamp,
        latestProductTimestamp,
        collectionType,
      });
    } else if (latestOrderTimestamp || latestProductTimestamp) {
      // Use the latest data timestamp as starting point
      const latestTimestamp =
        latestOrderTimestamp && latestProductTimestamp
          ? new Date(
              Math.max(
                latestOrderTimestamp.getTime(),
                latestProductTimestamp.getTime()
              )
            )
          : latestOrderTimestamp || latestProductTimestamp;

      sinceDate = latestTimestamp!.toISOString();
      collectionType = "incremental_since_latest_data";
      Logger.info("Collecting incremental data since latest data timestamp", {
        sinceDate,
        latestOrderTimestamp,
        latestProductTimestamp,
        collectionType,
      });
    } else {
      // Fallback to configured days if no timestamps exist
      sinceDate = calculateSinceDate(DATA_COLLECTION_CONFIG.FALLBACK_DAYS);
      collectionType = "incremental_fallback";
      Logger.info("Collecting incremental data since fallback date", {
        sinceDate,
        daysBack: DATA_COLLECTION_CONFIG.FALLBACK_DAYS,
        collectionType,
      });
    }

    // Create Shopify API instance
    const shopifyApi = createShopifyAxiosInstance(config.shopifyApi);

    // Collect incremental orders and products in parallel for better performance
    Logger.info(
      "Fetching incremental orders and products from Shopify GraphQL API in parallel",
      {
        shopDomain,
        sinceDate,
      }
    );

    const parallelStartTime = Date.now();

    // Execute both API calls simultaneously
    const [orders, products] = await Promise.all([
      fetchOrders(shopifyApi, sinceDate),
      fetchProducts(shopifyApi, sinceDate),
    ]);
    const customers = await fetchCustomers(shopifyApi, sinceDate);

    const parallelDuration = Date.now() - parallelStartTime;

    Logger.performance(
      "Parallel incremental data collection",
      parallelDuration,
      {
        shopDomain,
        ordersCount: orders.length,
        productsCount: products.length,
        customersCount: customers.length,
      }
    );

    Logger.info("Incremental data collection completed", {
      ordersCount: orders.length,
      productsCount: products.length,
      totalDuration: Date.now() - startTime,
    });

    // Save incremental data to database in parallel - no transformation needed
    await Promise.all([
      saveProducts(config.database, shopDbId, products, true),
      saveOrders(config.database, shopDbId, orders, true),
      saveCustomers(config.database, shopDbId, customers, true),
    ]);

    // Update shop's last analysis timestamp
    await updateShopLastAnalysis(config.database, shopDbId);

    const totalDuration = Date.now() - startTime;
    Logger.performance(
      "Incremental data collection and saving",
      totalDuration,
      {
        shopId,
        shopDomain,
        productsSaved: products.length,
        ordersSaved: orders.length,
      }
    );

    Logger.info(
      "Incremental data collection and saving completed successfully",
      {
        shopId,
        shopDomain,
        productsSaved: products.length,
        ordersSaved: orders.length,
        totalDuration,
      }
    );

    return {
      orders,
      products,
      customers,
      shopDbId,
    };
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("Incremental data collection failed", {
      shopId,
      shopDomain,
      totalDuration,
      error,
    });

    throw error;
  }
};
