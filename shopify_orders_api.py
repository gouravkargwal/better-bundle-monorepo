import requests
import json
from typing import Dict, Any, Optional


class ShopifyOrdersAPI:
    def __init__(self, shop_domain: str, access_token: str):
        """
        Initialize the Shopify Orders API client

        Args:
            shop_domain: The shop domain (e.g., 'vnsaid.myshopify.com')
            access_token: The Shopify access token
        """
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.base_url = f"https://{shop_domain}/admin/api/2024-01/graphql.json"

    def get_orders(
        self, first: int = 1, after: Optional[str] = None, query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch orders from Shopify using GraphQL API

        Args:
            first: Number of orders to fetch (default: 1)
            after: Cursor for pagination
            query: Search query for filtering orders

        Returns:
            Dictionary containing the API response
        """

        # GraphQL query
        graphql_query = """
        query($first: Int!, $after: String, $query: String) {
          orders(first: $first, after: $after, query: $query) {
            pageInfo {
              hasNextPage
              hasPreviousPage
              startCursor
              endCursor
            }
            edges {
              cursor
              node {
                id
                name
                email
                phone
                createdAt
                updatedAt
                processedAt
                cancelledAt
                cancelReason
                totalPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                subtotalPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalTaxSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalShippingPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalRefundedSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                totalOutstandingSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
                customer {
                  id
                  firstName
                  lastName
                  displayName
                  email
                  phone
                  tags
                  createdAt
                  updatedAt
                  state
                  verifiedEmail
                  defaultAddress {
                    id
                    address1
                    city
                    province
                    country
                    zip
                    phone
                    provinceCode
                    countryCodeV2
                  }
                }
                lineItems(first: 10) {
                  edges {
                    node {
                      id
                      title
                      quantity
                      originalUnitPriceSet {
                        shopMoney {
                          amount
                          currencyCode
                        }
                      }
                      discountedUnitPriceSet {
                        shopMoney {
                          amount
                          currencyCode
                        }
                      }
                      variant {
                        id
                        title
                        price
                        sku
                        barcode
                        taxable
                        inventoryPolicy
                        position
                        createdAt
                        updatedAt
                        product {
                          id
                          title
                          productType
                          vendor
                          tags
                        }
                      }
                    }
                  }
                }
                fulfillments {
                  id
                  status
                  createdAt
                  updatedAt
                  displayStatus
                }
                transactions {
                  id
                  kind
                  status
                  amount
                  gateway
                  createdAt
                  processedAt
                }
                shippingAddress {
                  address1
                  city
                  province
                  country
                  zip
                  phone
                  provinceCode
                  countryCodeV2
                }
                billingAddress {
                  address1
                  city
                  province
                  country
                  zip
                  phone
                  provinceCode
                  countryCodeV2
                }
                tags
                note
                confirmed
                test
                customerLocale
                currencyCode
                presentmentCurrencyCode
                discountApplications(first: 5) {
                  edges {
                    node {
                      value {
                        ... on MoneyV2 {
                          amount
                          currencyCode
                        }
                        ... on PricingPercentageValue {
                          percentage
                        }
                      }
                    }
                  }
                }
                metafields(first: 10) {
                  edges {
                    node {
                      id
                      namespace
                      key
                      value
                      type
                    }
                  }
                }
              }
            }
          }
        }
        """

        # Prepare variables
        variables = {"first": first}

        if after:
            variables["after"] = after
        if query:
            variables["query"] = query

        # Prepare the request payload
        payload = {"query": graphql_query, "variables": variables}

        # Set up headers
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token,
        }

        try:
            # Make the API request
            response = requests.post(
                self.base_url, headers=headers, json=payload, timeout=30
            )

            # Check if the request was successful
            response.raise_for_status()

            # Parse the JSON response
            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                print(f"GraphQL Errors: {data['errors']}")
                return data

            return data

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return {"error": str(e)}
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            return {"error": f"Invalid JSON response: {e}"}


def main():
    """
    Main function to demonstrate the API usage
    """
    # Configuration
    SHOP_DOMAIN = "vnsaid.myshopify.com"
    ACCESS_TOKEN = "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"

    # Initialize the API client
    api = ShopifyOrdersAPI(SHOP_DOMAIN, ACCESS_TOKEN)

    # Fetch 1 order
    print("Fetching 1 order from Shopify...")
    result = api.get_orders(first=1)

    # Print the result
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print("Success! Order data:")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
