/// <reference types="vite/client" />
/// <reference types="@remix-run/node" />

declare namespace NodeJS {
  interface ProcessEnv {
    // Observability / OpenObserve
    OPENOBSERVE_ENDPOINT?: string;
    OPENOBSERVE_ORG?: string;
    OPENOBSERVE_API_KEY?: string;

    // App
    NODE_ENV?: string;
    LOG_LEVEL?: string;

    // Shopify
    SHOPIFY_API_KEY?: string;
    SHOPIFY_API_SECRET?: string;
    SCOPES?: string;
    SHOPIFY_APP_URL?: string;
    SHOP_CUSTOM_DOMAIN?: string;
    SHOPIFY_APP_HANDLE?: string;

    // Redis
    REDIS_URL?: string;
    REDIS_HOST?: string;
    REDIS_PORT?: string;
    REDIS_PASSWORD?: string;
    REDIS_DB?: string;

    // Kafka
    KAFKA_BOOTSTRAP_SERVERS?: string;
    KAFKA_CLIENT_ID?: string;
    KAFKA_WORKER_ID?: string;

    // Python Worker
    PYTHON_WORKER_API_URL?: string;

    // Server
    HOST?: string;
    FRONTEND_PORT?: string;
    PORT?: string;
  }
}
