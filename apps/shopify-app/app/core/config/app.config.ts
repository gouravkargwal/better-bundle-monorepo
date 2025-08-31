export interface AppConfig {
  apiUrl: string;
  environment: "development" | "staging" | "production";
  features: {
    appBridge: boolean;
    cors: boolean;
    logging: boolean;
  };
}

// Environment-based configuration
const getConfig = (): AppConfig => {
  const env = process.env.NODE_ENV || "development";
  const isDev = env === "development";

  // In production, this would be your actual domain
  const productionApiUrl =
    process.env.PRODUCTION_API_URL || "https://your-production-domain.com";
  // Use Cloudflare tunnel URL from shopify.app.toml or environment variable
  const developmentApiUrl =
    process.env.DEVELOPMENT_API_URL ||
    "https://def-undergraduate-pdf-interstate.trycloudflare.com";

  return {
    apiUrl: isDev ? developmentApiUrl : productionApiUrl,
    environment: env as "development" | "staging" | "production",
    features: {
      appBridge: true,
      cors: true,
      logging: isDev,
    },
  };
};

export const appConfig = getConfig();

// Helper function to get the widget API URL
export const getWidgetApiUrl = (): string => {
  return `${appConfig.apiUrl}/api/widget`;
};

// Helper function to check if we're in development
export const isDevelopment = (): boolean => {
  return appConfig.environment === "development";
};

// Helper function to get environment-specific settings
export const getEnvironmentConfig = () => {
  return {
    ...appConfig,
    widgetApiUrl: getWidgetApiUrl(),
  };
};
