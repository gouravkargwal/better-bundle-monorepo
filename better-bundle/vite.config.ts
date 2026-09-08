import { vitePlugin as remix } from "@remix-run/dev";
import { installGlobals } from "@remix-run/node";
import { defineConfig, type UserConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

installGlobals({ nativeFetch: true });

// Related: https://github.com/remix-run/remix/issues/2835#issuecomment-1144102176
// Replace the HOST env var with SHOPIFY_APP_URL so that it doesn't break the remix server. The CLI will eventually
// stop passing in HOST, so we can remove this workaround after the next major release.
if (
  process.env.HOST &&
  (!process.env.SHOPIFY_APP_URL ||
    process.env.SHOPIFY_APP_URL === process.env.HOST)
) {
  process.env.SHOPIFY_APP_URL = process.env.HOST;
  delete process.env.HOST;
}

const host = new URL(process.env.SHOPIFY_APP_URL || "http://localhost")
  .hostname;

const port = Number(process.env.PORT || 3000);

let hmrConfig;
if (host === "localhost") {
  hmrConfig = {
    protocol: "ws",
    host: "localhost",
    port: 64999,
    clientPort: 64999,
  };
} else {
  // Through a tunnel the HMR socket has to share the app's port, because that
  // is the only one forwarded; the browser then reaches it on 443. This used to
  // read a separate FRONTEND_PORT, which could only ever hold the same value as
  // PORT and silently broke hot reload when it did not.
  hmrConfig = {
    protocol: "wss",
    host: host,
    port: port,
    clientPort: 443,
  };
}

export default defineConfig({
  server: {
    // Vite rejects requests whose Host header it does not recognise. `host` is
    // derived from SHOPIFY_APP_URL, which goes stale the moment the CLI hands
    // out a new tunnel — so the wildcards matter more than the exact value.
    // A leading dot matches any subdomain.
    allowedHosts: [host, ".trycloudflare.com", ".ngrok-free.app", ".ngrok.app", ".ngrok.io"],
    cors: {
      preflightContinue: true,
    },
    port: port,
    hmr: hmrConfig,
    fs: {
      // See https://vitejs.dev/config/server-options.html#server-fs-allow for more information
      allow: ["app", "node_modules"],
    },
    watch: {
      usePolling: true,
    },
  },
  plugins: [
    remix({
      ignoredRouteFiles: ["**/.*"],
      future: {
        v3_fetcherPersist: true,
        v3_relativeSplatPath: true,
        v3_throwAbortReason: true,
        v3_lazyRouteDiscovery: true,
        v3_singleFetch: false,
        v3_routeConfig: true,
      },
    }),
    tsconfigPaths(),
  ],
  build: {
    assetsInlineLimit: 0,
  },
  optimizeDeps: {
    include: ["@shopify/app-bridge-react", "@shopify/polaris"],
  },
}) satisfies UserConfig;
