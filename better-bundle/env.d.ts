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
  }
}
