import type { ProductRecommendationAPI } from "../types";

export const formatPrice = (
  amount: number | string,
  currencyCode: string,
): string => {
  const numAmount = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode,
  }).format(numAmount);
};

export const isProductEligible = (
  product: ProductRecommendationAPI,
): boolean => {
  return product.available && product.inventory > 0;
};

export const getShopifyErrorMessage = (code: string): string => {
  const errorMessages: Record<string, string> = {
    insufficient_inventory: "This product is out of stock",
    payment_required: "Payment authorization is required",
    unsupported_payment_method:
      "Your payment method doesn't support adding products",
    subscription_vaulting_error: "Cannot add subscription products",
    changeset_already_applied: "This product has already been added",
    order_released_error:
      "Your order has been processed and cannot be modified",
  };
  return errorMessages[code] || "Unable to add product to order";
};
