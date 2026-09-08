import { useState, useEffect, useMemo } from "react";
import {
  getRecommendations,
  type ProductRecommendation,
  type ExtensionContext,
} from "../api/recommendations";
import { reportClick } from "../api/attribution";
import { useApi } from "@shopify/ui-extensions-react/customer-account";
import { logger } from "../utils/logger";

// Format price using the same logic as the Remix app
const formatPrice = (amount: string, currencyCode: string): string => {
  try {
    const numericAmount = parseFloat(amount);

    // Use Intl.NumberFormat for proper currency formatting (same as Remix app)
    const formatter = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits:
        currencyCode === "JPY" || currencyCode === "KRW" ? 0 : 2,
      maximumFractionDigits:
        currencyCode === "JPY" || currencyCode === "KRW" ? 0 : 2,
    });

    return formatter.format(numericAmount);
  } catch (error) {
    // Fallback to simple symbol + amount
    const currencySymbols: { [key: string]: string } = {
      USD: "$",
      EUR: "€",
      GBP: "£",
      CAD: "C$",
      AUD: "A$",
      JPY: "¥",
      INR: "₹",
      KRW: "₩",
      BRL: "R$",
      MXN: "$",
    };
    const symbol = currencySymbols[currencyCode] || currencyCode;
    return `${symbol}${amount}`;
  }
};

interface Product {
  id: string;
  title: string;
  handle: string;
  price: string;
  image: {
    url: string;
    alt_text?: string;
  } | null;
  images?: Array<{
    url: string;
    alt_text?: string;
    type?: string;
    position?: number;
  }>;
  inStock: boolean;
  url: string;
  variant_id?: string;
  impressionId?: string;
}

interface UseRecommendationsProps {
  context: ExtensionContext;
  limit: number;
  customerId: string;
  shopDomain?: string;
  columnConfig: {
    extraSmall: number;
    small: number;
    medium: number;
    large: number;
  };
}

export function useRecommendations({
  context,
  limit,
  customerId,
  shopDomain,
  columnConfig,
}: UseRecommendationsProps) {
  const { storage } = useApi();
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);

  // No session bootstrap.
  //
  // The endpoint that backed it is gone, and nothing here needs it. Holdout
  // bucketing keys on `customerId`, which a customer account extension always
  // has because the shopper is signed in — so unlike the storefront there is
  // no anonymous visitor to identify and no device storage to consent to.
  //
  // Attribution keys on the impression id returned with each recommendation.

  // Memoized column configuration
  const memoizedColumnConfig = useMemo(() => columnConfig, [columnConfig]);

  // Report a click-through, then hand back the URL to navigate to.
  //
  // Venus has no cart, so this is the only outcome it can observe: the shopper
  // will add the product on its own page using the theme's button. The backend
  // reconciles the click against the order later by checking whether this
  // exact product was bought inside the attribution window.
  const trackRecommendationClick = async (
    productId: string,
    position: number,
    productUrl: string,
    impressionId?: string,
  ): Promise<string> => {
    if (storage && impressionId) {
      // Not awaited beyond the call itself; navigation follows immediately and
      // the request is sent with keepalive.
      await reportClick(storage, impressionId);
    }
    return productUrl;
  };

  // Fetch recommendations
  useEffect(() => {
    if (!storage) {
      return;
    }

    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await getRecommendations(storage, {
          context,
          limit,
          user_id: customerId,
          shop_domain: shopDomain,
        });

        if (response.success && response.recommendations) {
          // Transform API response to component format
          const transformedProducts: Product[] = response.recommendations.map(
            (rec: ProductRecommendation) => ({
              id: rec.id,
              title: rec.title,
              handle: rec.handle,
              price: formatPrice(rec.price.amount, rec.price.currency_code),
              image: rec.image,
              images: rec.images || [],
              inStock: rec.available ?? true,
              url:
                rec.url ||
                (shopDomain
                  ? `https://${shopDomain}/products/${rec.handle}`
                  : rec.handle),
              variants: rec.variants || [],
              // Returned by the serve path; required to attribute a click.
              impressionId: rec.impression_id,
            }),
          );

          setProducts(transformedProducts);
        } else {
          throw new Error(`Failed to fetch ${context} recommendations`);
        }
      } catch (err) {
        logger.error(
          {
            error: err instanceof Error ? err.message : String(err),
            shop_domain: shopDomain,
          },
          "Failed to fetch recommendations",
        );
        setError("Failed to load recommendations");
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [customerId, context, limit, shopDomain, storage]);

  return {
    loading,
    products,
    error,
    trackRecommendationClick,
    columnConfig: memoizedColumnConfig,
  };
}
