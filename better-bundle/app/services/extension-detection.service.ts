import { getWidgetConfiguration } from "../services/widget-config.service";

// Helper function to get page configuration values
function getPageConfigValue(
  config: any,
  pageType: string,
  property: string,
): any {
  if (!config) return null;

  const propertyMap: Record<string, Record<string, string>> = {
    product_page: {
      enabled: "productPageEnabled",
      title: "productPageTitle",
      limit: "productPageLimit",
      showPrices: "productPageShowPrices",
      showReasons: "productPageShowReasons",
    },
    cart_page: {
      enabled: "cartPageEnabled",
      title: "cartPageTitle",
      limit: "cartPageLimit",
      showPrices: "cartPageShowPrices",
      showReasons: "cartPageShowReasons",
    },
    homepage: {
      enabled: "homepageEnabled",
      title: "homepageTitle",
      limit: "homepageLimit",
      showPrices: "homepageShowPrices",
      showReasons: "homepageShowReasons",
    },
    collection: {
      enabled: "collectionPageEnabled",
      title: "collectionPageTitle",
      limit: "collectionPageLimit",
      showPrices: "collectionPageShowPrices",
      showReasons: "collectionPageShowReasons",
    },
    search: {
      enabled: "searchPageEnabled",
      title: "searchPageTitle",
      limit: "searchPageLimit",
      showPrices: "searchPageShowPrices",
      showReasons: "searchPageShowReasons",
    },
    blog: {
      enabled: "blogPageEnabled",
      title: "blogPageTitle",
      limit: "blogPageLimit",
      showPrices: "blogPageShowPrices",
      showReasons: "blogPageShowReasons",
    },
    checkout: {
      enabled: "checkoutPageEnabled",
      title: "checkoutPageTitle",
      limit: "checkoutPageLimit",
      showPrices: "checkoutPageShowPrices",
      showReasons: "checkoutPageShowReasons",
    },
    account: {
      enabled: "accountPageEnabled",
      title: "accountPageTitle",
      limit: "accountPageLimit",
      showPrices: "accountPageShowPrices",
      showReasons: "accountPageShowReasons",
    },
  };

  const pageConfig = propertyMap[pageType];
  if (!pageConfig || !pageConfig[property]) return null;

  return config[pageConfig[property]];
}

export interface PageStatus {
  pageType: string;
  isActive: boolean;
  templateFile?: string;
  sectionName?: string;
  configuration?: {
    enabled: boolean;
    title: string;
    limit: number;
    showPrices: boolean;
    showReasons: boolean;
  };
}

export interface ExtensionInstallationStatus {
  isInstalled: boolean;
  themeId?: string;
  themeName?: string;
  lastChecked: Date;
  error?: string;
  pageStatuses: PageStatus[];
}

// Multi-theme extension status check - checks all relevant themes
export async function getMultiThemeExtensionStatus(
  shopDomain: string,
  admin: any,
  session: any,
): Promise<{
  isInstalled: boolean;
  isAvailable: boolean;
  themeId?: string;
  themeName?: string;
  lastChecked: Date;
  error?: string;
  pageStatuses: PageStatus[];
  blockUsage: { hasAppBlocks: boolean; locations: string[] };
  pageConfigs: Record<string, any>;
  shopDomain: string;
  multiThemeStatus?: Array<{
    themeId: string;
    themeName: string;
    role: string;
    hasAppBlocks: boolean;
    locations: string[];
    pageStatuses: PageStatus[];
    error?: string;
  }>;
}> {
  if (!admin) {
    return {
      isInstalled: false,
      isAvailable: false,
      lastChecked: new Date(),
      error: "No admin client provided",
      pageStatuses: [],
      blockUsage: { hasAppBlocks: false, locations: [] },
      pageConfigs: {},
      shopDomain,
    };
  }

  try {
    console.log(`🔧 Multi-theme extension check for shop: ${shopDomain}`);

    // Get widget configuration and page configs
    const pageConfigs = await getPageConfigurationStatus(shopDomain);

    // Check extension availability
    const isAvailable = await checkExtensionAvailability(shopDomain, admin);

    // Get themes
    const query = `
      query getThemes {
        themes(first: 20) {
          edges {
            node {
              id
              name
              role
            }
          }
        }
      }
    `;

    const response = await admin.graphql(query);
    const data = await response.json();

    if (data.errors) {
      console.error("GraphQL errors:", data.errors);
      return {
        isInstalled: false,
        isAvailable,
        lastChecked: new Date(),
        error: `GraphQL error: ${data.errors[0]?.message || "Unknown error"}`,
        pageStatuses: [],
        blockUsage: { hasAppBlocks: false, locations: [] },
        pageConfigs,
        shopDomain,
      };
    }

    const themes = data.data?.themes?.edges || [];
    console.log(
      `📋 Found ${themes.length} themes:`,
      themes.map((t: any) => ({
        name: t.node.name,
        role: t.node.role,
        id: t.node.id,
      })),
    );

    // Filter to relevant themes (main, live, unpublished)
    const relevantThemes = themes.filter((themeEdge: any) => {
      const role = themeEdge.node.role;
      return role === "main" || role === "live" || role === "unpublished";
    });

    console.log(`📋 Found ${relevantThemes.length} relevant themes to check`);

    // If no relevant themes, use all themes as fallback
    const themesToCheck = relevantThemes.length > 0 ? relevantThemes : themes;

    if (themesToCheck.length === 0) {
      return {
        isInstalled: false,
        isAvailable,
        lastChecked: new Date(),
        error: "No themes found",
        pageStatuses: [],
        blockUsage: { hasAppBlocks: false, locations: [] },
        pageConfigs,
        shopDomain,
      };
    }

    // For single theme, use simple logic
    if (themesToCheck.length === 1) {
      const theme = themesToCheck[0].node;
      console.log(`📋 Using single theme: ${theme.name} (${theme.role})`);

      const blockUsage = await checkAppBlockUsageAccurate(
        shopDomain,
        theme.id,
        admin,
        session,
      );
      const pageStatuses = await checkPageSpecificInstallationsAccurate(
        shopDomain,
        theme.id,
        admin,
        session,
      );

      return {
        isInstalled: blockUsage.hasAppBlocks,
        isAvailable,
        themeId: theme.id,
        themeName: theme.name,
        lastChecked: new Date(),
        pageStatuses,
        blockUsage,
        pageConfigs,
        shopDomain,
      };
    }

    // For multiple themes, check all and provide comprehensive status
    console.log(`🔍 Checking extension across ${themesToCheck.length} themes`);

    const themeStatuses = [];
    let hasAnyAppBlocks = false;
    const allPageStatuses: any[] = [];
    const allLocations: string[] = [];

    for (const themeEdge of themesToCheck) {
      const theme = themeEdge.node;
      console.log(`🔍 Checking theme: ${theme.name} (${theme.role})`);

      try {
        const blockUsage = await checkAppBlockUsageAccurate(
          shopDomain,
          theme.id,
          admin,
          session,
        );
        const pageStatuses = await checkPageSpecificInstallationsAccurate(
          shopDomain,
          theme.id,
          admin,
          session,
        );

        themeStatuses.push({
          themeId: theme.id,
          themeName: theme.name,
          role: theme.role,
          hasAppBlocks: blockUsage.hasAppBlocks,
          locations: blockUsage.locations,
          pageStatuses,
        });

        if (blockUsage.hasAppBlocks) {
          hasAnyAppBlocks = true;
          allLocations.push(...blockUsage.locations);
        }
        allPageStatuses.push(...pageStatuses);
      } catch (error) {
        console.error(`Error checking theme ${theme.name}:`, error);
        themeStatuses.push({
          themeId: theme.id,
          themeName: theme.name,
          role: theme.role,
          hasAppBlocks: false,
          locations: [],
          pageStatuses: [],
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    // Find the primary theme (main > live > unpublished)
    const primaryTheme =
      themesToCheck.find((t: any) => t.node.role === "main") ||
      themesToCheck.find((t: any) => t.node.role === "live") ||
      themesToCheck[0];

    return {
      isInstalled: hasAnyAppBlocks,
      isAvailable,
      themeId: primaryTheme.node.id,
      themeName: primaryTheme.node.name,
      lastChecked: new Date(),
      pageStatuses: allPageStatuses,
      blockUsage: { hasAppBlocks: hasAnyAppBlocks, locations: allLocations },
      pageConfigs,
      shopDomain,
      multiThemeStatus: themeStatuses,
    };
  } catch (error) {
    console.error("Error in multi-theme extension check:", error);
    return {
      isInstalled: false,
      isAvailable: false,
      lastChecked: new Date(),
      error: "Unable to check extension status",
      pageStatuses: [],
      blockUsage: { hasAppBlocks: false, locations: [] },
      pageConfigs: {},
      shopDomain,
    };
  }
}

// Keep the original function for backward compatibility
export async function checkExtensionInstallation(
  shopDomain: string,
  admin: any,
  session: any,
): Promise<ExtensionInstallationStatus> {
  if (!admin) {
    return {
      isInstalled: false,
      lastChecked: new Date(),
      error: "No admin client provided for API calls",
      pageStatuses: [],
    };
  }

  try {
    console.log(`🔧 Checking extension installation for shop: ${shopDomain}`);

    // Query themes (removed sortKey as it’s not supported)
    const query = `
      query getThemes {
        themes(first: 10) {
          edges {
            node {
              id
              name
              role
            }
          }
        }
      }
    `;

    const response = await admin.graphql(query);
    const data = await response.json();

    if (data.errors) {
      throw new Error(`GraphQL errors: ${JSON.stringify(data.errors)}`);
    }

    const themes = data.data?.themes?.edges || [];
    // Sort themes by updated_at manually if needed (since sortKey is not supported)
    const mainTheme = themes.find(
      (edge: any) => edge.node.role === "main",
    )?.node;

    if (!mainTheme) {
      return {
        isInstalled: false,
        lastChecked: new Date(),
        error: "No main theme found",
        pageStatuses: [],
      };
    }

    console.log(`📋 Found main theme: ${mainTheme.name} (${mainTheme.id})`);

    // Check for app blocks in the main theme using accurate REST API method
    const { hasAppBlocks } = await checkAppBlockUsageAccurate(
      shopDomain,
      mainTheme.id,
      admin,
      session,
    );

    // Get page-specific installation statuses using accurate REST API method
    const pageStatuses = await checkPageSpecificInstallationsAccurate(
      shopDomain,
      mainTheme.id,
      admin,
      session,
    );

    return {
      isInstalled: hasAppBlocks,
      themeId: mainTheme.id,
      themeName: mainTheme.name,
      lastChecked: new Date(),
      pageStatuses,
    };
  } catch (error) {
    console.error("Error checking extension installation:", error);
    return {
      isInstalled: false,
      lastChecked: new Date(),
      error: "Unable to check extension status",
      pageStatuses: [],
    };
  }
}

// Helper function to check JSON content for app blocks
export function checkJsonForAppBlocks(
  jsonContent: any,
  appBlockId: string,
): boolean {
  const traverse = (obj: any): boolean => {
    if (!obj || typeof obj !== "object") return false;

    // Check if this object contains our app block ID
    const jsonString = JSON.stringify(obj);
    if (jsonString.includes(appBlockId)) {
      return true;
    }

    // Recursively check all values
    return Object.values(obj).some((value) => traverse(value));
  };

  return traverse(jsonContent);
}

// 100% Accurate App Block Detection using REST API
export async function checkAppBlockUsageAccurate(
  shopDomain: string,
  themeId: string,
  admin: any,
  session: any,
): Promise<{ hasAppBlocks: boolean; locations: string[] }> {
  if (!admin) {
    return { hasAppBlocks: false, locations: [] };
  }

  try {
    console.log(`🔍 Accurate app block detection for theme: ${themeId}`);

    // Your app's unique block identifier
    const appBlockId =
      "shopify://apps/better-bundle/blocks/phoenix/ebf2bbf3-ac07-95dc-4552-0633f958c425ea14e806";

    const locations: string[] = [];

    // Key template files to check (4 core pages only)
    const templateFiles = [
      "templates/product.json",
      "templates/index.json",
      "templates/collection.json",
      "templates/cart.json",
    ];

    // Check each template file
    for (const templateFile of templateFiles) {
      try {
        console.log(`📄 Checking template: ${templateFile}`);

        // Use REST API to get file content
        const response = await fetch(
          `https://${shopDomain}/admin/api/2025-07/themes/${themeId}/assets.json?asset[key]=${templateFile}`,
          {
            headers: {
              "X-Shopify-Access-Token": session.accessToken,
              "Content-Type": "application/json",
            },
          },
        );

        if (response.ok) {
          const asset = await response.json();

          if (asset.asset && asset.asset.value) {
            try {
              const jsonContent = JSON.parse(asset.asset.value);

              // Check if this file contains our app block
              if (checkJsonForAppBlocks(jsonContent, appBlockId)) {
                locations.push(templateFile);
                console.log(`✅ Found app block in: ${templateFile}`);
              }
            } catch (parseError) {
              console.log(
                `⚠️ Could not parse JSON for ${templateFile}:`,
                parseError,
              );
            }
          }
        } else {
          console.log(`⚠️ Could not fetch ${templateFile}: ${response.status}`);
        }
      } catch (error) {
        console.log(`⚠️ Error checking ${templateFile}:`, error);
      }
    }

    // Also check settings_data.json for app block configuration
    try {
      console.log(`📄 Checking settings_data.json`);
      const response = await fetch(
        `https://${shopDomain}/admin/api/2025-07/themes/${themeId}/assets.json?asset[key]=config/settings_data.json`,
        {
          headers: {
            "X-Shopify-Access-Token": session.accessToken,
            "Content-Type": "application/json",
          },
        },
      );

      if (response.ok) {
        const asset = await response.json();

        if (asset.asset && asset.asset.value) {
          try {
            const jsonContent = JSON.parse(asset.asset.value);

            if (checkJsonForAppBlocks(jsonContent, appBlockId)) {
              locations.push("config/settings_data.json");
              console.log(`✅ Found app block in: config/settings_data.json`);
            }
          } catch (parseError) {
            console.log(`⚠️ Could not parse settings_data.json:`, parseError);
          }
        }
      }
    } catch (error) {
      console.log(`⚠️ Error checking settings_data.json:`, error);
    }

    const hasAppBlocks = locations.length > 0;
    console.log(
      `🎯 Accurate detection result: ${hasAppBlocks ? "FOUND" : "NOT FOUND"} in ${locations.length} file(s)`,
    );

    return { hasAppBlocks, locations };
  } catch (error) {
    console.error("Error in accurate app block detection:", error);
    throw new Error("Unable to check app block usage");
  }
}

// 100% Accurate Page-Specific Detection using REST API
export async function checkPageSpecificInstallationsAccurate(
  shopDomain: string,
  themeId: string,
  admin: any,
  session: any,
): Promise<PageStatus[]> {
  if (!admin) {
    return [];
  }

  try {
    console.log(`🔍 Accurate page-specific detection for theme: ${themeId}`);

    // Your app's unique block identifier
    const appBlockId =
      "shopify://apps/better-bundle/blocks/phoenix/ebf2bbf3-ac07-95dc-4552-0633f958c425ea14e806";

    // Get widget configuration for page settings
    const config = await getWidgetConfiguration(shopDomain);

    // Define page types and their corresponding template files (4 core pages only)
    const pageTypes = [
      {
        type: "product_page",
        templateFile: "templates/product.json",
        displayName: "Product Page",
      },
      {
        type: "homepage",
        templateFile: "templates/index.json",
        displayName: "Homepage",
      },
      {
        type: "collection",
        templateFile: "templates/collection.json",
        displayName: "Collection Page",
      },
      {
        type: "cart_page",
        templateFile: "templates/cart.json",
        displayName: "Cart Page",
      },
    ];

    const pageStatuses: PageStatus[] = [];

    // Check each page type
    for (const pageType of pageTypes) {
      const pageStatus: PageStatus = {
        pageType: pageType.type,
        isActive: false,
        templateFile: pageType.templateFile,
        configuration: {
          enabled:
            getPageConfigValue(config, pageType.type, "enabled") || false,
          title:
            getPageConfigValue(config, pageType.type, "title") ||
            "You Might Also Like",
          limit: getPageConfigValue(config, pageType.type, "limit") || 6,
          showPrices:
            getPageConfigValue(config, pageType.type, "showPrices") || true,
          showReasons:
            getPageConfigValue(config, pageType.type, "showReasons") || true,
        },
      };

      try {
        console.log(
          `📄 Checking ${pageType.displayName}: ${pageType.templateFile}`,
        );

        // Use REST API to get file content
        const response = await fetch(
          `https://${shopDomain}/admin/api/2025-07/themes/${themeId}/assets.json?asset[key]=${pageType.templateFile}`,
          {
            headers: {
              "X-Shopify-Access-Token": session.accessToken,
              "Content-Type": "application/json",
            },
          },
        );

        if (response.ok) {
          const asset = await response.json();

          if (asset.asset && asset.asset.value) {
            try {
              const jsonContent = JSON.parse(asset.asset.value);

              // Check if this file contains our app block
              if (checkJsonForAppBlocks(jsonContent, appBlockId)) {
                pageStatus.isActive = true;
                pageStatus.sectionName = "phoenix";
                console.log(`✅ Found app block in ${pageType.displayName}`);
              } else {
                console.log(`❌ No app block found in ${pageType.displayName}`);
              }
            } catch (parseError) {
              console.log(
                `⚠️ Could not parse JSON for ${pageType.templateFile}:`,
                parseError,
              );
            }
          } else {
            console.log(`⚠️ No content found for ${pageType.templateFile}`);
          }
        } else {
          console.log(
            `⚠️ Could not fetch ${pageType.templateFile}: ${response.status}`,
          );
        }
      } catch (error) {
        console.log(`⚠️ Error checking ${pageType.templateFile}:`, error);
      }

      pageStatuses.push(pageStatus);
    }

    const activePages = pageStatuses.filter((p) => p.isActive).length;
    console.log(
      `🎯 Page-specific detection: ${activePages}/${pageStatuses.length} pages have the extension active`,
    );

    return pageStatuses;
  } catch (error) {
    console.error("Error in accurate page-specific detection:", error);
    throw new Error("Unable to check page-specific installations");
  }
}

export async function checkExtensionAvailability(
  shopDomain: string,
  admin: any,
): Promise<boolean> {
  try {
    // Debug logging removed - enableDebug property not available in schema

    const query = `
      query getCurrentAppInstallation {
        currentAppInstallation {
          id
          app {
            id
            title
            embedded
          }
        }
      }
    `;

    const response = await admin.graphql(query);
    const data = await response.json();

    if (data.errors) {
      console.error("GraphQL errors:", data.errors);
      return false;
    }

    const isAvailable = !!data.data?.currentAppInstallation?.app?.embedded;
    if (isAvailable) {
      console.log("App installation found, extension available");
    }
    return isAvailable;
  } catch (error) {
    console.error("Error checking extension availability:", error);
    throw new Error("Unable to check extension availability");
  }
}

export async function getPageConfigurationStatus(
  shopDomain: string,
): Promise<Record<string, any>> {
  try {
    const config = await getWidgetConfiguration(shopDomain);
    return {
      product_page: {
        enabled: config?.productPageEnabled || false,
        title: config?.productPageTitle || "You Might Also Like",
        limit: config?.productPageLimit || 6,
        showPrices: config?.productPageShowPrices || true,
        showReasons: config?.productPageShowReasons || true,
      },
      homepage: {
        enabled: config?.homepageEnabled || false,
        title: config?.homepageTitle || "Popular Products",
        limit: config?.homepageLimit || 8,
        showPrices: config?.homepageShowPrices || true,
        showReasons: config?.homepageShowReasons || true,
      },
      collection: {
        enabled: config?.collectionPageEnabled || false,
        title: config?.collectionPageTitle || "You Might Also Like",
        limit: config?.collectionPageLimit || 6,
        showPrices: config?.collectionPageShowPrices || true,
        showReasons: config?.collectionPageShowReasons || true,
      },
      cart_page: {
        enabled: config?.cartPageEnabled || false,
        title: config?.cartPageTitle || "Frequently Bought Together",
        limit: config?.cartPageLimit || 4,
        showPrices: config?.cartPageShowPrices || true,
        showReasons: config?.cartPageShowReasons || true,
      },
    };
  } catch (error) {
    console.error("Error getting page configuration status:", error);
    throw new Error("Unable to get page configuration status");
  }
}
