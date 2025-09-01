import axios, { AxiosInstance } from "axios";
import { Logger } from "../utils/logger";

export interface DatabaseOrder {
  orderId: string;
  totalAmount: {
    shopMoney: {
      amount: string;
    };
  };
  orderDate: string;
  customerId?: {
    id: string;
  };
  lineItems: {
    edges: Array<{
      node: {
        productId: {
          id: string;
        };
        variantId: {
          id: string;
        };
        title: string;
        quantity: number;
        price: {
          price: string;
        };
      };
    }>;
  };
}

export interface DatabaseProduct {
  id: string;
  title: string;
  handle: string;
  product_type: string;
  tags: string[];
  image?: {
    src: string;
    alt: string;
  };
  variants: Array<{
    id: string;
    price: string;
    inventory_quantity: number;
  }>;
}

export interface GraphQLResponse<T> {
  data: {
    [key: string]: {
      pageInfo: {
        hasNextPage: boolean;
        endCursor: string;
      };
      edges: Array<{
        node: T;
      }>;
    };
  };
}

export interface ShopifyApiConfig {
  shopId: string;
  shopDomain: string;
  accessToken: string;
}

// Create axios instance with interceptors
export const createShopifyAxiosInstance = (
  config: ShopifyApiConfig
): AxiosInstance => {
  const axiosInstance = axios.create({
    baseURL: `https://${config.shopDomain}/admin/api/2024-01`,
    headers: {
      "X-Shopify-Access-Token": config.accessToken,
      "Content-Type": "application/json",
    },
    timeout: 30000,
  });

  // Add request interceptor for logging
  axiosInstance.interceptors.request.use(
    (config) => {
      Logger.debug("Shopify API Request", {
        method: config.method?.toUpperCase(),
        url: config.url,
        shopDomain: config.baseURL,
      });
      return config;
    },
    (error) => {
      Logger.error("Shopify API Request Error", error);
      return Promise.reject(error);
    }
  );

  // Add response interceptor for logging
  axiosInstance.interceptors.response.use(
    (response) => {
      Logger.debug("Shopify API Response", {
        status: response.status,
        url: response.config.url,
        shopDomain: response.config.baseURL,
      });
      return response;
    },
    (error) => {
      Logger.error("Shopify API Response Error", {
        status: error.response?.status,
        message: error.message,
        url: error.config?.url,
        shopDomain: error.config?.baseURL,
      });
      return Promise.reject(error);
    }
  );

  return axiosInstance;
};

// Execute GraphQL query with error handling
export const executeGraphQLQuery = async <T>(
  axiosInstance: AxiosInstance,
  query: string,
  variables: Record<string, any>
): Promise<GraphQLResponse<T>> => {
  try {
    const response = await axiosInstance.post("/graphql.json", {
      query,
      variables,
    });

    if (response.data.errors) {
      Logger.error("GraphQL errors received", {
        errors: response.data.errors,
        query: query.substring(0, 200) + "...",
        variables,
      });
      throw new Error(
        `GraphQL errors: ${JSON.stringify(response.data.errors)}`
      );
    }

    return response.data;
  } catch (error) {
    Logger.error("GraphQL query execution failed", {
      query: query.substring(0, 100) + "...",
      variables,
      error,
    });
    throw error;
  }
};

// Fetch orders with configurable data amount
export const fetchOrders = async (
  axiosInstance: AxiosInstance,
  sinceDate?: string,
  limit?: number
): Promise<DatabaseOrder[]> => {
  const query = `
    query getOrders($query: String, $after: String, $first: Int) {
      orders(query: $query, after: $after, first: $first) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            orderId: id
            totalAmount: totalPriceSet {
              shopMoney {
                amount
              }
            }
            orderDate: createdAt
            customerId: customer {
              id
            }
            lineItems(first: 50) {
              edges {
                node {
                  productId: product {
                    id
                  }
                  variantId: variant {
                    id
                  }
                  title
                  quantity
                  price: variant {
                    price
                  }
                }
              }
            }
          }
        }
      }
    }
  `;

  const allOrders: DatabaseOrder[] = [];
  let hasNextPage = true;
  let cursor: string | null = null;
  let totalFetched = 0;

  while (hasNextPage && (!limit || totalFetched < limit)) {
    const remainingLimit = limit ? limit - totalFetched : undefined;
    const batchSize = remainingLimit ? Math.min(remainingLimit, 250) : 250;

    const response = await executeGraphQLQuery<DatabaseOrder>(
      axiosInstance,
      query,
      {
        query: sinceDate ? `created_at:>='${sinceDate}'` : undefined,
        after: cursor,
        first: batchSize,
      }
    );

    const ordersResponse: any = response.data.orders;
    const edges = ordersResponse.edges || [];

    // Direct data storage - no mapping needed
    allOrders.push(...edges.map((edge: any) => edge.node));
    totalFetched += edges.length;

    hasNextPage = ordersResponse.pageInfo.hasNextPage;
    cursor = ordersResponse.pageInfo.endCursor;

    Logger.info("Orders pagination progress", {
      ordersCollected: allOrders.length,
      totalFetched,
      limit,
      hasNextPage,
      cursor: cursor ? cursor.substring(0, 20) + "..." : null,
    });

    // Stop if we've reached the limit
    if (limit && totalFetched >= limit) {
      break;
    }
  }

  return allOrders;
};

// Fetch products with configurable data amount
export const fetchProducts = async (
  axiosInstance: AxiosInstance,
  sinceDate?: string,
  limit?: number
): Promise<DatabaseProduct[]> => {
  const query = `
    query getProducts($query: String, $after: String, $first: Int) {
      products(query: $query, after: $after, first: $first) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            id
            title
            handle
            product_type: productType
            tags
            image: images(first: 1) {
              edges {
                node {
                  src: url
                  alt: altText
                }
              }
            }
            variants(first: 10) {
              edges {
                node {
                  id
                  price
                  inventory_quantity: inventoryQuantity
                }
              }
            }
          }
        }
      }
    }
  `;

  const allProducts: DatabaseProduct[] = [];
  let hasNextPage = true;
  let cursor: string | null = null;
  let totalFetched = 0;

  while (hasNextPage && (!limit || totalFetched < limit)) {
    const remainingLimit = limit ? limit - totalFetched : undefined;
    const batchSize = remainingLimit ? Math.min(remainingLimit, 250) : 250;

    const response = await executeGraphQLQuery<DatabaseProduct>(
      axiosInstance,
      query,
      {
        query: sinceDate ? `updated_at:>='${sinceDate}'` : undefined,
        after: cursor,
        first: batchSize,
      }
    );

    const productsResponse: any = response.data.products;
    const edges = productsResponse.edges || [];

    // Direct data storage - no mapping needed
    allProducts.push(...edges.map((edge: any) => edge.node));
    totalFetched += edges.length;

    hasNextPage = productsResponse.pageInfo.hasNextPage;
    cursor = productsResponse.pageInfo.endCursor;

    Logger.info("Products pagination progress", {
      productsCollected: allProducts.length,
      totalFetched,
      limit,
      hasNextPage,
      cursor: cursor ? cursor.substring(0, 20) + "..." : null,
    });

    // Stop if we've reached the limit
    if (limit && totalFetched >= limit) {
      break;
    }
  }

  return allProducts;
};
