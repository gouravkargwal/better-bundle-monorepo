import { prisma } from "../../../core/database/prisma.server";

export class PrivateAppDataCollectionService {
  private shopDomain: string;
  private accessToken: string;

  constructor() {
    this.shopDomain = process.env.SHOP_DOMAIN || "";
    this.accessToken = process.env.SHOPIFY_ACCESS_TOKEN || "";
  }

  /**
   * Initialize shop data collection using private app
   */
  async initializeShopData(): Promise<{
    success: boolean;
    error?: string;
    errorType?: string;
    ordersCollected?: number;
    productsCollected?: number;
  }> {
    try {
      if (!this.shopDomain || !this.accessToken) {
        return {
          success: false,
          error: "Missing SHOP_DOMAIN or SHOPIFY_ACCESS_TOKEN in environment",
          errorType: "api-error",
        };
      }

      // Fetch shop information including currency
      const shopInfo = await this.fetchShopInfo();

      // Ensure shop exists in database first
      let shop = await prisma.shop.findUnique({
        where: { shopId: this.shopDomain },
      });

      if (!shop) {
        // Create shop record if it doesn't exist
        shop = await prisma.shop.create({
          data: {
            shopId: this.shopDomain,
            shopDomain: this.shopDomain,
            accessToken: this.accessToken,
            planType: "Free",
            currencyCode: shopInfo.currencyCode,
            moneyFormat: shopInfo.currencyFormats?.moneyFormat || "{{amount}}",
          },
        });
      } else {
        // Update existing shop with currency info if not present
        if (!shop.currencyCode) {
          shop = await prisma.shop.update({
            where: { id: shop.id },
            data: {
              currencyCode: shopInfo.currencyCode,
              moneyFormat:
                shopInfo.currencyFormats?.moneyFormat || "{{amount}}",
            },
          });
        }
      }

      // Collect both order and product data
      // Note: If one fails, the entire process fails to avoid partial data
      await Promise.all([
        this.collectOrderData(shop.id),
        this.collectProductData(shop.id),
      ]);

      // Get counts for reporting
      const orderCount = await prisma.orderData.count({
        where: { shopId: shop.id },
      });
      const productCount = await prisma.productData.count({
        where: { shopId: shop.id },
      });

      // Debug: Let's see what's actually in the database
      const sampleOrders = await prisma.orderData.findMany({
        where: { shopId: shop.id },
        take: 3,
        select: { orderId: true, lineItems: true },
      });

      console.log(`🔍 Debug - Sample orders from database:`, {
        orderCount,
        productCount,
        sampleOrders: sampleOrders.map((order) => ({
          orderId: order.orderId,
          lineItemsCount: Array.isArray(order.lineItems)
            ? order.lineItems.length
            : 0,
          sampleLineItems: Array.isArray(order.lineItems)
            ? order.lineItems.slice(0, 2).map((item: any, index: number) => {
                console.log(
                  `🔍 Line Item ${index + 1}:`,
                  JSON.stringify(item, null, 2),
                );
                return {
                  productId: item?.productId,
                  productIdType: typeof item?.productId,
                  hasProductId: !!item?.productId,
                  product: item?.product,
                  variant: item?.variant,
                  quantity: item?.quantity,
                  price: item?.price,
                  availableKeys: Object.keys(item || {}),
                };
              })
            : [],
        })),
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

      return {
        success: true,
        ordersCollected: orderCount,
        productsCollected: productCount,
      };
    } catch (error) {
      console.error(
        `Error initializing shop data for ${this.shopDomain}:`,
        error,
      );
      return {
        success: false,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
        errorType: "api-error",
      };
    }
  }

  /**
   * Collect order data from Shopify using private app
   */
  private async collectOrderData(
    shopId: string,
    daysBack: number = 180,
  ): Promise<void> {
    try {
      // Calculate date range
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - daysBack);

      const orders = await this.fetchOrdersFromShopify(startDate, endDate);
      await this.storeOrders(shopId, orders);
    } catch (error) {
      console.error(
        `Error collecting order data for shop ${this.shopDomain}:`,
        error,
      );
      throw error;
    }
  }

  /**
   * Collect product data from Shopify using private app
   */
  private async collectProductData(shopId: string): Promise<void> {
    try {
      const products = await this.fetchProductsFromShopify();
      await this.storeProducts(shopId, products);
    } catch (error) {
      console.error(
        `Error collecting product data for shop ${this.shopDomain}:`,
        error,
      );
      throw error;
    }
  }

  /**
   * Fetch orders from Shopify using private app
   */
  private async fetchOrdersFromShopify(
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
              # customer {
              #   id
              # }
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

    const response = await fetch(
      `https://${this.shopDomain}/admin/api/2025-01/graphql.json`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Access-Token": this.accessToken,
        },
        body: JSON.stringify({ query }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Shopify API error: ${response.status} ${response.statusText}`,
      );
    }

    const data = await response.json();

    if (data.errors) {
      throw new Error(`GraphQL errors: ${JSON.stringify(data.errors)}`);
    }

    return data.data.orders.edges.map((edge: any) => edge.node);
  }

  /**
   * Make authenticated request to Shopify GraphQL API
   */
  private async shopifyRequest(
    query: string,
    variables: any = {},
  ): Promise<any> {
    const response = await fetch(
      `https://${this.shopDomain}/admin/api/2025-01/graphql.json`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Access-Token": this.accessToken,
        },
        body: JSON.stringify({ query, variables }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Shopify API error: ${response.status} ${response.statusText}`,
      );
    }

    const data = await response.json();

    if (data.errors) {
      throw new Error(`GraphQL errors: ${JSON.stringify(data.errors)}`);
    }

    return data;
  }

  /**
   * Fetch shop information from Shopify
   */
  private async fetchShopInfo(): Promise<any> {
    const query = `
      query {
        shop {
          id
          name
          myshopifyDomain
          currencyCode
          currencyFormats {
            moneyFormat
          }
        }
      }
    `;

    const response = await this.shopifyRequest(query);
    return response.data.shop;
  }

  /**
   * Fetch products from Shopify using private app
   */
  private async fetchProductsFromShopify(): Promise<any[]> {
    const query = `
      query getProducts {
        products(first: 250) {
          edges {
            node {
              id
              title
              handle
              description
              images(first: 1) {
                edges {
                  node {
                    url
                  }
                }
              }
              variants(first: 10) {
                edges {
                  node {
                    id
                    title
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

    const response = await fetch(
      `https://${this.shopDomain}/admin/api/2025-01/graphql.json`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Access-Token": this.accessToken,
        },
        body: JSON.stringify({ query }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Shopify API error: ${response.status} ${response.statusText}`,
      );
    }

    const data = await response.json();

    if (data.errors) {
      throw new Error(`GraphQL errors: ${JSON.stringify(data.errors)}`);
    }

    return data.data.products.edges.map((edge: any) => edge.node);
  }

  /**
   * Store orders in database
   */
  private async storeOrders(shopId: string, orders: any[]): Promise<void> {
    // Store new order data using upsert to avoid duplicates
    for (const order of orders) {
      const lineItems =
        order.lineItems?.edges?.map((edge: any) => edge.node) || [];

      // Store order with line items as JSON
      await prisma.orderData.upsert({
        where: {
          shopId_orderId: {
            shopId,
            orderId: order.id,
          },
        },
        update: {
          customerId: null, // We removed customer access
          totalAmount: parseFloat(
            order.totalPriceSet?.shopMoney?.amount || "0",
          ),
          orderDate: new Date(order.createdAt),
          lineItems: lineItems, // Store as JSON
        },
        create: {
          shopId,
          orderId: order.id,
          customerId: null, // We removed customer access
          totalAmount: parseFloat(
            order.totalPriceSet?.shopMoney?.amount || "0",
          ),
          orderDate: new Date(order.createdAt),
          lineItems: lineItems, // Store as JSON
        },
      });
    }
  }

  /**
   * Store products in database
   */
  private async storeProducts(shopId: string, products: any[]): Promise<void> {
    // Store new product data using upsert to avoid duplicates
    for (const product of products) {
      const variants =
        product.variants?.edges?.map((edge: any) => edge.node) || [];

      // Use the first variant's price as the product price
      const firstVariant = variants[0];
      const price = firstVariant ? parseFloat(firstVariant.price || "0") : 0;

      // Sum up inventory across all variants
      const totalInventory = variants.reduce((sum: number, variant: any) => {
        return sum + (variant.inventoryQuantity || 0);
      }, 0);

      // Get product image
      const firstImage = product.images?.edges?.[0]?.node;
      const imageUrl = firstImage?.url || null;
      const imageAlt = product.title || null;

      await prisma.productData.upsert({
        where: {
          shopId_productId: {
            shopId,
            productId: product.id,
          },
        },
        update: {
          title: product.title,
          handle: product.handle,
          price: price,
          inventory: totalInventory,
          imageUrl: imageUrl,
          imageAlt: imageAlt,
          isActive: true,
        },
        create: {
          shopId,
          productId: product.id,
          title: product.title,
          handle: product.handle,
          price: price,
          inventory: totalInventory,
          imageUrl: imageUrl,
          imageAlt: imageAlt,
          isActive: true,
        },
      });
    }
  }
}
