import { PrismaClient } from '@prisma/client';
import axios from 'axios';

const prisma = new PrismaClient();

async function testShopifyAPI(shopDomain) {
  console.log(`🧪 Testing Shopify API for shop: ${shopDomain}`);

  try {
    // Get the current session and shop data (check for online token first)
    let session = await prisma.session.findFirst({
      where: {
        shop: shopDomain,
        isOnline: true
      }
    });

    // Fallback to offline token if no online token found
    if (!session) {
      session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` }
      });
    }

    if (!session) {
      console.log(`❌ No session found for ${shopDomain}`);
      return;
    }

    console.log(`📋 Session found:`, {
      id: session.id,
      shop: session.shop,
      scope: session.scope,
      accessToken: session.accessToken ? `${session.accessToken.substring(0, 20)}...` : 'null',
      isOnline: session.isOnline
    });

    // Get shop record
    const shop = await prisma.shop.findUnique({
      where: { shopDomain }
    });

    if (!shop) {
      console.log(`❌ No shop record found for ${shopDomain}`);
      return;
    }

    console.log(`🏪 Shop record found:`, {
      id: shop.id,
      shopDomain: shop.shopDomain,
      accessToken: shop.accessToken ? `${shop.accessToken.substring(0, 20)}...` : 'null'
    });

    // Test 1: Get shop information
    console.log(`\n🔍 Test 1: Getting shop information...`);
    try {
      const shopResponse = await axios.get(
        `https://${shopDomain}/admin/api/2024-01/shop.json`,
        {
          headers: {
            'X-Shopify-Access-Token': session.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        }
      );

      console.log(`✅ Shop API call successful!`);
      console.log(`📊 Shop data:`, {
        name: shopResponse.data.shop.name,
        email: shopResponse.data.shop.email,
        domain: shopResponse.data.shop.domain,
        currency: shopResponse.data.shop.currency
      });
    } catch (error) {
      console.log(`❌ Shop API call failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message
      });
    }

    // Test 2: Get orders (this is what the analysis needs)
    console.log(`\n🔍 Test 2: Getting orders...`);
    try {
      // Calculate date 50 days ago (matching fly-worker)
      const fiftyDaysAgo = new Date();
      fiftyDaysAgo.setDate(fiftyDaysAgo.getDate() - 50);
      const sinceDate = fiftyDaysAgo.toISOString().split("T")[0];

      console.log(`📅 Requesting orders since: ${sinceDate} (50 days ago)`);

      // Try without problematic status=any parameter
      const ordersResponse = await axios.get(
        `https://${shopDomain}/admin/api/2024-01/orders.json?created_at_min=${sinceDate}&limit=250`,
        {
          headers: {
            'X-Shopify-Access-Token': session.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        }
      );

      console.log(`✅ Orders API call successful!`);
      console.log(`📊 Orders data:`, {
        totalOrders: ordersResponse.data.orders?.length || 0,
        firstOrder: ordersResponse.data.orders?.[0] ? {
          id: ordersResponse.data.orders[0].id,
          order_number: ordersResponse.data.orders[0].order_number,
          total_price: ordersResponse.data.orders[0].total_price,
          created_at: ordersResponse.data.orders[0].created_at
        } : null
      });
    } catch (error) {
      console.log(`❌ Orders API call failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        url: error.config?.url
      });
    }

    // Test 2.1: Try orders without date filter and without problematic parameters
    console.log(`\n🔍 Test 2.1: Getting orders without date filter...`);
    try {
      const ordersResponse2 = await axios.get(
        `https://${shopDomain}/admin/api/2024-01/orders.json?limit=250`,
        {
          headers: {
            'X-Shopify-Access-Token': session.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        }
      );

      console.log(`✅ Orders API call (no date filter) successful!`);
      console.log(`📊 Orders data:`, {
        totalOrders: ordersResponse2.data.orders?.length || 0,
        firstOrder: ordersResponse2.data.orders?.[0] ? {
          id: ordersResponse2.data.orders[0].id,
          order_number: ordersResponse2.data.orders[0].order_number,
          total_price: ordersResponse2.data.orders[0].total_price,
          created_at: ordersResponse2.data.orders[0].created_at
        } : null
      });
    } catch (error) {
      console.log(`❌ Orders API call (no date filter) failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        url: error.config?.url
      });
    }

    // Test 2.2: Try with different API version
    console.log(`\n🔍 Test 2.2: Getting orders with 2023-10 API version...`);
    try {
      const ordersResponse3 = await axios.get(
        `https://${shopDomain}/admin/api/2023-10/orders.json?limit=5`,
        {
          headers: {
            'X-Shopify-Access-Token': session.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        }
      );

      console.log(`✅ Orders API call (2023-10) successful!`);
      console.log(`📊 Orders data:`, {
        totalOrders: ordersResponse3.data.orders?.length || 0,
        firstOrder: ordersResponse3.data.orders?.[0] ? {
          id: ordersResponse3.data.orders[0].id,
          order_number: ordersResponse3.data.orders[0].order_number,
          total_price: ordersResponse3.data.orders[0].total_price,
          created_at: ordersResponse3.data.orders[0].created_at
        } : null
      });
    } catch (error) {
      console.log(`❌ Orders API call (2023-10) failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        url: error.config?.url
      });
    }

    // Test 2.3: Try with shop record access token
    console.log(`\n🔍 Test 2.3: Getting orders with shop record access token...`);
    try {
      const ordersResponse4 = await axios.get(
        `https://${shopDomain}/admin/api/2024-01/orders.json?limit=250`,
        {
          headers: {
            'X-Shopify-Access-Token': shop.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        }
      );

      console.log(`✅ Orders API call (shop token) successful!`);
      console.log(`📊 Orders data:`, {
        totalOrders: ordersResponse4.data.orders?.length || 0,
        firstOrder: ordersResponse4.data.orders?.[0] ? {
          id: ordersResponse4.data.orders[0].id,
          order_number: ordersResponse4.data.orders[0].order_number,
          total_price: ordersResponse4.data.orders[0].total_price,
          created_at: ordersResponse4.data.orders[0].created_at
        } : null
      });
    } catch (error) {
      console.log(`❌ Orders API call (shop token) failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        url: error.config?.url
      });
    }

    // Test 2.4: Try REST API with pagination
    console.log(`\n🔍 Test 2.4: Getting orders with REST API pagination...`);
    try {
      let allRestOrders = [];
      let hasNextPage = true;
      let pageInfo = null;
      let pageCount = 0;

      while (hasNextPage) {
        pageCount++;
        console.log(`📄 REST API Page ${pageCount}...`);

        const url = pageInfo?.next_page_info
          ? `https://${shopDomain}/admin/api/2024-01/orders.json?limit=250&page_info=${pageInfo.next_page_info}`
          : `https://${shopDomain}/admin/api/2024-01/orders.json?limit=250`;

        const restResponse = await axios.get(url, {
          headers: {
            'X-Shopify-Access-Token': session.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        });

        const orders = restResponse.data.orders || [];
        allRestOrders = allRestOrders.concat(orders);

        // Check for pagination headers
        const linkHeader = restResponse.headers.link;
        hasNextPage = linkHeader && linkHeader.includes('rel="next"');

        // Extract next page info from Link header
        if (linkHeader) {
          const nextMatch = linkHeader.match(/<[^>]*page_info=([^&>]+)[^>]*>;\s*rel="next"/);
          if (nextMatch) {
            pageInfo = { next_page_info: nextMatch[1] };
          } else {
            pageInfo = null;
          }
        } else {
          pageInfo = null;
        }

        console.log(`📊 REST Page ${pageCount}: ${orders.length} orders, Total: ${allRestOrders.length}, Has next: ${hasNextPage}`);

        // Safety break to prevent infinite loops
        if (pageCount > 10) {
          console.log(`⚠️ Stopping pagination after 10 pages for safety`);
          break;
        }
      }

      console.log(`✅ REST API pagination successful!`);
      console.log(`📊 REST API orders data:`, {
        totalOrders: allRestOrders.length,
        totalPages: pageCount,
        firstOrder: allRestOrders[0] ? {
          id: allRestOrders[0].id,
          order_number: allRestOrders[0].order_number,
          total_price: allRestOrders[0].total_price,
          created_at: allRestOrders[0].created_at
        } : null,
        lastOrder: allRestOrders[allRestOrders.length - 1] ? {
          id: allRestOrders[allRestOrders.length - 1].id,
          order_number: allRestOrders[allRestOrders.length - 1].order_number,
          total_price: allRestOrders[allRestOrders.length - 1].total_price,
          created_at: allRestOrders[allRestOrders.length - 1].created_at
        } : null
      });
    } catch (error) {
      console.log(`❌ REST API pagination failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        url: error.config?.url
      });
    }

    // Test 2.5: Comparing access tokens...
    console.log(`\n🔍 Test 2.5: Comparing access tokens...`);
    const sessionTokenStart = session.accessToken.substring(0, 20);
    const shopTokenStart = shop.accessToken.substring(0, 20);
    console.log(`📋 Session token starts with: ${sessionTokenStart}...`);
    console.log(`📋 Shop token starts with: ${shopTokenStart}...`);
    console.log(`📋 Tokens are ${sessionTokenStart === shopTokenStart ? 'identical' : 'different'}`);

    // Test 2.6: Try GraphQL orders query with pagination (60 days)
    console.log(`\n🔍 Test 2.6: Getting orders via GraphQL with pagination (60 days)...`);
    try {
      // Calculate date 60 days ago
      const sixtyDaysAgo = new Date();
      sixtyDaysAgo.setDate(sixtyDaysAgo.getDate() - 60);
      const sinceDate = sixtyDaysAgo.toISOString().split("T")[0];

      console.log(`📅 Requesting orders since: ${sinceDate} (60 days ago)`);

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
      let allOrders = [];
      let hasNextPage = true;
      let cursor = null;
      let pageCount = 0;

      while (hasNextPage) {
        pageCount++;
        console.log(`📄 Fetching page ${pageCount}...`);

        const graphqlResponse = await axios.post(
          `https://${shopDomain}/admin/api/2024-01/graphql.json`,
          {
            query: graphqlQuery,
            variables: {
              query: `created_at:>='${sinceDate}'`,
              after: cursor
            }
          },
          {
            headers: {
              'X-Shopify-Access-Token': session.accessToken,
              'Content-Type': 'application/json',
            },
            timeout: 30000
          }
        );

        const responseData = graphqlResponse.data.data?.orders;
        const edges = responseData?.edges || [];

        allOrders = allOrders.concat(edges);

        hasNextPage = responseData?.pageInfo?.hasNextPage || false;
        cursor = responseData?.pageInfo?.endCursor || null;

        console.log(`📊 Page ${pageCount}: ${edges.length} orders, Total: ${allOrders.length}, Has next: ${hasNextPage}`);
      }

      console.log(`✅ GraphQL orders query with pagination successful!`);
      console.log(`📊 GraphQL orders data:`, {
        totalOrders: allOrders.length,
        totalPages: pageCount,
        firstOrder: allOrders[0]?.node ? {
          id: allOrders[0].node.id,
          name: allOrders[0].node.name,
          createdAt: allOrders[0].node.createdAt,
          totalPrice: allOrders[0].node.totalPriceSet?.shopMoney?.amount,
          lineItemsCount: allOrders[0].node.lineItems?.edges?.length || 0
        } : null,
        lastOrder: allOrders[allOrders.length - 1]?.node ? {
          id: allOrders[allOrders.length - 1].node.id,
          name: allOrders[allOrders.length - 1].node.name,
          createdAt: allOrders[allOrders.length - 1].node.createdAt,
          totalPrice: allOrders[allOrders.length - 1].node.totalPriceSet?.shopMoney?.amount
        } : null
      });
    } catch (error) {
      console.log(`❌ GraphQL orders query failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        errors: error.response?.data?.errors
      });
    }

    // Test 2.7: Try GraphQL orders query without date filter
    console.log(`\n🔍 Test 2.7: Getting ALL orders via GraphQL (no date filter)...`);
    try {
      const graphqlQuery2 = `
        query getOrders($after: String) {
          orders(first: 250, after: $after) {
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

      // Also test a simpler query first
      console.log(`\n🔍 Test 2.7.1: Simple GraphQL orders query...`);
      try {
        const simpleQuery = `
          query {
            orders(first: 10) {
              edges {
                node {
                  id
                  name
                  createdAt
                }
              }
            }
          }
        `;

        const simpleResponse = await axios.post(
          `https://${shopDomain}/admin/api/2024-01/graphql.json`,
          { query: simpleQuery },
          {
            headers: {
              'X-Shopify-Access-Token': "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",
              'Content-Type': 'application/json',
            },
            timeout: 30000
          }
        );

        console.log(`✅ Simple GraphQL query successful!`);
        console.log(`📊 Simple query data:`, {
          totalOrders: simpleResponse.data.data?.orders?.edges?.length || 0,
          firstOrder: simpleResponse.data.data?.orders?.edges?.[0]?.node ? {
            id: simpleResponse.data.data.orders.edges[0].node.id,
            name: simpleResponse.data.data.orders.edges[0].node.name,
            createdAt: simpleResponse.data.data.orders.edges[0].node.createdAt
          } : null
        });
      } catch (error) {
        console.log(`❌ Simple GraphQL query failed:`, {
          status: error.response?.status,
          statusText: error.response?.statusText,
          message: error.message,
          errors: error.response?.data?.errors
        });
      }

      // Collect all orders using pagination
      let allOrders2 = [];
      let hasNextPage2 = true;
      let cursor2 = null;
      let pageCount2 = 0;

      while (hasNextPage2) {
        pageCount2++;
        console.log(`📄 Fetching page ${pageCount2}...`);

        const graphqlResponse2 = await axios.post(
          `https://${shopDomain}/admin/api/2024-01/graphql.json`,
          {
            query: graphqlQuery2,
            variables: {
              after: cursor2
            }
          },
          {
            headers: {
              'X-Shopify-Access-Token': session.accessToken,
              'Content-Type': 'application/json',
            },
            timeout: 30000
          }
        );

        const responseData2 = graphqlResponse2.data.data?.orders;
        const edges2 = responseData2?.edges || [];

        allOrders2 = allOrders2.concat(edges2);

        hasNextPage2 = responseData2?.pageInfo?.hasNextPage || false;
        cursor2 = responseData2?.pageInfo?.endCursor || null;

        console.log(`📊 Page ${pageCount2}: ${edges2.length} orders, Total: ${allOrders2.length}, Has next: ${hasNextPage2}`);
      }

      console.log(`✅ GraphQL ALL orders query successful!`);
      console.log(`📊 GraphQL ALL orders data:`, {
        totalOrders: allOrders2.length,
        totalPages: pageCount2,
        firstOrder: allOrders2[0]?.node ? {
          id: allOrders2[0].node.id,
          name: allOrders2[0].node.name,
          createdAt: allOrders2[0].node.createdAt,
          totalPrice: allOrders2[0].node.totalPriceSet?.shopMoney?.amount,
          lineItemsCount: allOrders2[0].node.lineItems?.edges?.length || 0
        } : null,
        lastOrder: allOrders2[allOrders2.length - 1]?.node ? {
          id: allOrders2[allOrders2.length - 1].node.id,
          name: allOrders2[allOrders2.length - 1].node.name,
          createdAt: allOrders2[allOrders2.length - 1].node.createdAt,
          totalPrice: allOrders2[allOrders2.length - 1].node.totalPriceSet?.shopMoney?.amount
        } : null
      });
    } catch (error) {
      console.log(`❌ GraphQL ALL orders query failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message,
        errors: error.response?.data?.errors
      });
    }

    // Test 3: Get products
    console.log(`\n🔍 Test 3: Getting products...`);
    try {
      const productsResponse = await axios.get(
        `https://${shopDomain}/admin/api/2024-01/products.json?limit=5`,
        {
          headers: {
            'X-Shopify-Access-Token': session.accessToken,
            'Content-Type': 'application/json',
          },
          timeout: 10000
        }
      );

      console.log(`✅ Products API call successful!`);
      console.log(`📊 Products data:`, {
        totalProducts: productsResponse.data.products?.length || 0,
        firstProduct: productsResponse.data.products?.[0] ? {
          id: productsResponse.data.products[0].id,
          title: productsResponse.data.products[0].title,
          handle: productsResponse.data.products[0].handle,
          product_type: productsResponse.data.products[0].product_type
        } : null
      });
    } catch (error) {
      console.log(`❌ Products API call failed:`, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        message: error.message
      });
    }

    // Test 4: Check scopes
    console.log(`\n🔍 Test 4: Checking scopes...`);
    const requiredScopes = ['read_orders', 'read_products', 'write_orders', 'write_products'];
    const currentScopes = session.scope?.split(',') || [];

    console.log(`📋 Current scopes: ${session.scope}`);
    console.log(`📋 Required scopes: ${requiredScopes.join(', ')}`);

    const missingScopes = requiredScopes.filter(scope => !currentScopes.includes(scope));
    if (missingScopes.length > 0) {
      console.log(`❌ Missing scopes: ${missingScopes.join(', ')}`);
    } else {
      console.log(`✅ All required scopes are present!`);
    }

  } catch (error) {
    console.error(`❌ Error during API test:`, error);
  } finally {
    await prisma.$disconnect();
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('Usage: node scripts/test-shopify-api.js <shop-domain>');
  console.log('Example: node scripts/test-shopify-api.js vnsaid.myshopify.com');
  process.exit(1);
}

testShopifyAPI(shopDomain);
