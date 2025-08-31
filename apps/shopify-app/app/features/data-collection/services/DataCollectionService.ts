import { prisma } from "../../../core/database/prisma.server";

export class DataCollectionService {
  /**
   * Initialize shop data collection
   */
  async initializeShopData(
    shopId: string,
    admin: any,
  ): Promise<{
    success: boolean;
    error?: string;
    errorType?: string;
    ordersCollected?: number;
    productsCollected?: number;
  }> {
    try {
      console.log(`Initializing data collection for shop: ${shopId}`);

      // Ensure shop exists in database first
      let shop = await prisma.shop.findUnique({
        where: { shopId },
      });

      if (!shop) {
        // Create shop record if it doesn't exist
        shop = await prisma.shop.create({
          data: {
            shopId,
            shopDomain: shopId, // Using shopId as domain for now
            accessToken: "temp", // Will be updated by the main API route
            planType: "Free",
          },
        });
        console.log(`Created shop record for: ${shopId}`);
      }

      // Collect both order and product data
      await Promise.all([
        this.collectOrderData(shopId, admin),
        this.collectProductData(shopId, admin),
      ]);

      // Get counts for reporting
      const orderCount = await prisma.orderData.count({ where: { shopId } });
      const productCount = await prisma.productData.count({
        where: { shopId },
      });

      // Check if we have sufficient data
      if (orderCount === 0) {
        return {
          success: false,
          error: "No orders found in your store",
          errorType: "no-orders",
        };
      }

      if (orderCount < 5) {
        return {
          success: false,
          error: "Insufficient order data for meaningful analysis",
          errorType: "insufficient-data",
          ordersCollected: orderCount,
          productsCollected: productCount,
        };
      }

      console.log(`Data initialization completed for shop: ${shopId}`);
      return {
        success: true,
        ordersCollected: orderCount,
        productsCollected: productCount,
      };
    } catch (error) {
      console.error(`Error initializing shop data for ${shopId}:`, error);
      return {
        success: false,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        errorType: "api-error",
      };
    }
  }

  /**
   * Collect order data from Shopify for analysis
   */
  private async collectOrderData(
    shopId: string,
    admin: any,
    daysBack: number = 30, // Changed to 30 days
  ): Promise<void> {
    try {
      console.log(`Starting order data collection for shop: ${shopId}`);

      // Calculate date range
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - daysBack);

      const orders = await this.fetchOrdersFromShopify(
        admin,
        startDate,
        endDate,
      );

      // Clear existing order data for this shop
      await prisma.orderData.deleteMany({
        where: { shopId },
      });

      // Store new order data
      if (orders.length > 0) {
        const orderData = orders.map((order) => ({
          shopId,
          orderId: order.orderId,
          customerId: order.customerId,
          totalAmount: order.totalAmount,
          orderDate: order.orderDate,
          lineItems: order.lineItems,
        }));

        await prisma.orderData.createMany({
          data: orderData,
        });
      }

      console.log(`✅ Collected ${orders.length} orders for shop: ${shopId}`);
    } catch (error) {
      console.error(`Error collecting order data for shop ${shopId}:`, error);
      throw error;
    }
  }

  /**
   * Collect product data from Shopify for analysis
   */
  private async collectProductData(shopId: string, admin: any): Promise<void> {
    try {
      console.log(`Starting product data collection for shop: ${shopId}`);

      const products = await this.fetchProductsFromShopify(admin);

      // Clear existing product data for this shop
      await prisma.productData.deleteMany({
        where: { shopId },
      });

      // Store new product data
      if (products.length > 0) {
        const productData = products.map((product) => ({
          shopId,
          productId: product.productId,
          title: product.title,
          handle: product.handle,
          category: product.productType,
          price: product.price,
          tags: product.tags,
          imageUrl: product.imageUrl,
        }));

        await prisma.productData.createMany({
          data: productData,
        });
      }

      console.log(
        `✅ Collected ${products.length} products for shop: ${shopId}`,
      );
    } catch (error) {
      console.error(`Error collecting product data for shop ${shopId}:`, error);
      throw error;
    }
  }

  /**
   * Fetch orders from Shopify REST API
   */
  private async fetchOrdersFromShopify(
    admin: any,
    startDate: Date,
    endDate: Date,
  ): Promise<any[]> {
    const startDateStr = startDate.toISOString().split("T")[0];
    const endDateStr = endDate.toISOString().split("T")[0];

    // Use REST API instead of GraphQL
    const response = await admin.rest.get({
      path: `orders.json?status=any&created_at_min=${startDateStr}&created_at_max=${endDateStr}&limit=250`,
    });

    const orders = response.body.orders || [];

    return orders.map((order: any) => ({
      orderId: order.id.toString(),
      customerId: order.customer?.id?.toString(),
      totalAmount: parseFloat(order.total_price || "0"),
      orderDate: new Date(order.created_at),
      lineItems:
        order.line_items?.map((item: any) => ({
          productId: item.product_id?.toString(),
          variantId: item.variant_id?.toString(),
          price: parseFloat(item.price || "0"),
          quantity: item.quantity,
        })) || [],
    }));
  }

  /**
   * Fetch products from Shopify REST API
   */
  private async fetchProductsFromShopify(admin: any): Promise<any[]> {
    // Use REST API instead of GraphQL
    const response = await admin.rest.get({
      path: "products.json?limit=250",
    });

    const products = response.body.products || [];

    return products.map((product: any) => ({
      productId: product.id.toString(),
      title: product.title,
      handle: product.handle,
      productType: product.product_type,
      price: parseFloat(product.variants?.[0]?.price || "0"),
      tags: product.tags ? product.tags.split(", ") : [],
      imageUrl: product.image?.src || null,
    }));
  }
}
