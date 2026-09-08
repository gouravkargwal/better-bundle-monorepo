import '@shopify/ui-extensions';

//@ts-ignore
declare module './src/Checkout.jsx' {
  const shopify: import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/ThankYou.jsx' {
  const shopify: import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/hooks/useRecommendations.js' {
  const shopify:
    | import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api
    | import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/api/analytics.js' {
  const shopify:
    | import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api
    | import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/components/ProductCard.jsx' {
  const shopify: import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/utils/productUtils.js' {
  const shopify: import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/utils/logger.js' {
  const shopify:
    | import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api
    | import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/api/recommendations.js' {
  const shopify:
    | import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api
    | import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/config/constants.js' {
  const shopify:
    | import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api
    | import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}

//@ts-ignore
declare module './src/utils/jwt.js' {
  const shopify:
    | import('@shopify/ui-extensions/purchase.checkout.cart-line-list.render-after').Api
    | import('@shopify/ui-extensions/purchase.thank-you.cart-line-list.render-after').Api;
  const globalThis: { shopify: typeof shopify };
}
