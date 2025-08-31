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
    daysBack: number = 180,
  ): Promise<void> {
    try {
      console.log(`Starting order data collection for shop: ${shopId}`);

      // Calculate date range
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - daysBack);

      // Fetch orders from Shopify
      const orders = await this.fetchOrdersFromShopify(
        admin,
        startDate,
        endDate,
      );

      // Store orders in database
      await this.storeOrders(shopId, orders);

      console.log(
        `Order data collection completed for shop: ${shopId}. Collected ${orders.length} orders.`,
      );
    } catch (error) {
      console.error(`Error collecting order data for shop ${shopId}:`, error);
      throw error;
    }
  }

  /**
   * Collect product data from Shopify
   */
  private async collectProductData(shopId: string, admin: any): Promise<void> {
    try {
      console.log(`Starting product data collection for shop: ${shopId}`);

      // Fetch products from Shopify
      const products = await this.fetchProductsFromShopify(admin);

      // Store products in database
      await this.storeProducts(shopId, products);

      console.log(
        `Product data collection completed for shop: ${shopId}. Collected ${products.length} products.`,
      );
    } catch (error) {
      console.error(`Error collecting product data for shop ${shopId}:`, error);
      throw error;
    }
  }

  /**
   * Fetch orders from Shopify GraphQL API
   */
  private async fetchOrdersFromShopify(
    admin: any,
    startDate: Date,
    endDate: Date,
  ): Promise<any[]> {
    // Format dates for Shopify query
    const startDateStr = startDate.toISOString().split("T")[0];
    const endDateStr = endDate.toISOString().split("T")[0];

    const query = `
      query getOrders {
        orders(first: 250, query: "created_at:>='${startDateStr}' AND created_at:<='${endDateStr}'") {
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
                  }
                }
              }
            }
          }
        }
      }
    `;

    const response = await admin.graphql(query);
    const data = await response.json();

    return data.data.orders.edges.map((edge: any) => {
      const order = edge.node;
      return {
        orderId: order.id.split("/").pop(),
        customerId: order.customer?.id?.split("/").pop(),
        totalAmount: parseFloat(order.totalPriceSet.shopMoney.amount),
        orderDate: new Date(order.createdAt),
        lineItems: order.lineItems.edges.map((itemEdge: any) => ({
          productId: itemEdge.node.product?.id?.split("/").pop(),
          variantId: itemEdge.node.variant?.id?.split("/").pop(),
          price: parseFloat(itemEdge.node.variant?.price || "0"),
          quantity: itemEdge.node.quantity,
        })),
      };
    });
  }

  /**
   * Fetch products from Shopify GraphQL API
   */
  private async fetchProductsFromShopify(admin: any): Promise<any[]> {
    const query = `
      query getProducts {
        products(first: 250) {
          edges {
            node {
              id
              title
              handle
              productType
              tags
              variants(first: 10) {
                edges {
                  node {
                    id
                    price
                    inventoryQuantity
                  }
                }
              }
            }
          }
        }
      }
    `;

    const response = await admin.graphql(query);
    const data = await response.json();

    return data.data.products.edges.map((edge: any) => {
      const product = edge.node;
      const mainVariant = product.variants.edges[0]?.node;

      return {
        productId: product.id.split("/").pop(),
        title: product.title,
        handle: product.handle,
        category: product.productType,
        price: parseFloat(mainVariant?.price || "0"),
        inventory: mainVariant?.inventoryQuantity || 0,
        tags: product.tags || [],
      };
    });
  }

  /**
   * Store orders in database
   */
  private async storeOrders(shopId: string, orders: any[]): Promise<void> {
    // Clear existing order data for this shop
    await prisma.orderData.deleteMany({
      where: { shopId },
    });

    // Insert new order data
    if (orders.length > 0) {
      await prisma.orderData.createMany({
        data: orders.map((order) => ({
          shopId,
          orderId: order.orderId,
          customerId: order.customerId,
          totalAmount: order.totalAmount,
          orderDate: order.orderDate,
          lineItems: order.lineItems,
        })),
      });
    }
  }

  /**
   * Store products in database
   */
  private async storeProducts(shopId: string, products: any[]): Promise<void> {
    // Clear existing product data for this shop
    await prisma.productData.deleteMany({
      where: { shopId },
    });

    // Insert new product data
    if (products.length > 0) {
      await prisma.productData.createMany({
        data: products.map((product) => ({
          shopId,
          productId: product.productId,
          title: product.title,
          handle: product.handle,
          category: product.category,
          price: product.price,
          inventory: product.inventory,
          tags: product.tags,
        })),
      });
    }
  }
}
