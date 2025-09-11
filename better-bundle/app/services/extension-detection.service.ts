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

    // Filter to relevant themes (main, live, unpublished)
    const relevantThemes = themes.filter((themeEdge: any) => {
      const role = themeEdge.node.role;
      return role === "main" || role === "live" || role === "unpublished";
    });

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

    const themeStatuses = [];
    let hasAnyAppBlocks = false;
    const allPageStatuses: any[] = [];
    const allLocations: string[] = [];

    for (const themeEdge of themesToCheck) {
      const theme = themeEdge.node;

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

        // Consolidate page statuses - if a page is active in any theme, mark it as active
        pageStatuses.forEach((pageStatus: any) => {
          const existingIndex = allPageStatuses.findIndex(
            (existing: any) => existing.pageType === pageStatus.pageType,
          );

          if (existingIndex === -1) {
            // First time seeing this page type
            allPageStatuses.push(pageStatus);
          } else {
            // Update existing entry - if either is active, mark as active
            const existing = allPageStatuses[existingIndex];
            if (pageStatus.isActive || existing.isActive) {
              allPageStatuses[existingIndex] = {
                ...existing,
                isActive: true,
                // Keep the most recent template file info
                templateFile: pageStatus.templateFile || existing.templateFile,
                sectionName: pageStatus.sectionName || existing.sectionName,
              };
            }
          }
        });
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
      pageStatuses: allPageStatuses, // Use consolidated page statuses from all themes
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

// Optimized App Block Detection - Single API call for all assets
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
    // App block identifiers to search for
    const appBlockId =
      "shopify://apps/betterbundle/blocks/phoenix/0199379f-82d0-7b3b-9980-329260e4bf4b";

    // Extract numeric theme ID from GraphQL ID
    const numericThemeId = themeId.replace(
      "gid://shopify/OnlineStoreTheme/",
      "",
    );

    // Single API call to get all assets at once
    const response = await fetch(
      `https://${shopDomain}/admin/api/2024-07/themes/${numericThemeId}/assets.json`,
      {
        headers: {
          "X-Shopify-Access-Token": session.accessToken,
          "Content-Type": "application/json",
        },
      },
    );

    if (!response.ok) {
      return { hasAppBlocks: false, locations: [] };
    }

    const assetsData = await response.json();
    const assets = assetsData.assets || [];

    // Check ALL available files in the theme for app blocks (not just hardcoded ones)
    assets.filter((asset: any) => {
      const key = asset.key;
      // Check sections, templates, config, and layout files
      return (
        key.includes("sections/") ||
        key.includes("templates/") ||
        key.includes("config/") ||
        key.includes("layout/") ||
        key.endsWith(".liquid") ||
        key.endsWith(".json")
      );
    });

    try {
      // Use GraphQL to get theme template files where app blocks are stored
      const graphqlQuery = `
        query getThemeTemplateFiles($themeId: ID!) {
          theme(id: $themeId) {
            files(filenames: ["templates/product.json", "templates/collection.json", "templates/index.json", "templates/cart.json"]) {
              nodes {
                filename
                body {
                  ... on OnlineStoreThemeFileBodyText {
                    content
                  }
                }
              }
            }
          }
        }
      `;

      const graphqlResponse = await fetch(
        `https://${shopDomain}/admin/api/2024-07/graphql.json`,
        {
          method: "POST",
          headers: {
            "X-Shopify-Access-Token": session.accessToken,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: graphqlQuery,
            variables: { themeId: themeId },
          }),
        },
      );

      if (graphqlResponse.ok) {
        const graphqlData = await graphqlResponse.json();

        if (graphqlData.errors) {
          return {
            hasAppBlocks: false,
            locations: [],
          };
        }

        // Check template files for app blocks
        const templateFiles = graphqlData.data?.theme?.files?.nodes || [];
        let foundAppBlocks: string[] = [];
        let totalAppBlocks = 0;

        for (const file of templateFiles) {
          if (file.body?.content) {
            try {
              // Parse the JSON content (remove comments first)
              const cleanContent = file.body.content.replace(
                /\/\*[\s\S]*?\*\//g,
                "",
              );
              const templateData = JSON.parse(cleanContent);

              // Check sections for app blocks
              if (templateData.sections) {
                for (const [sectionId, section] of Object.entries(
                  templateData.sections,
                )) {
                  const sectionData = section as any;

                  // Check if this section has blocks
                  if (sectionData.blocks) {
                    for (const [blockId, block] of Object.entries(
                      sectionData.blocks,
                    )) {
                      const blockData = block as any;

                      // Check if this is our app block
                      if (
                        blockData.type &&
                        (blockData.type === appBlockId ||
                          blockData.type.includes("better-bundle") ||
                          blockData.type.includes("phoenix") ||
                          blockData.type.includes("bundle-recommendations"))
                      ) {
                        foundAppBlocks.push(
                          `${file.filename} -> ${sectionId} -> ${blockId}`,
                        );
                        totalAppBlocks++;
                      }
                    }
                  }
                }
              }
            } catch (parseError) {
              console.error(`⚠️ Could not parse ${file.filename}:`, parseError);
            }
          }
        }

        if (totalAppBlocks > 0) {
          return {
            hasAppBlocks: true,
            locations: foundAppBlocks,
          };
        } else {
          return {
            hasAppBlocks: false,
            locations: [],
          };
        }
      } else {
        return {
          hasAppBlocks: false,
          locations: [],
        };
      }
    } catch (error) {
      return {
        hasAppBlocks: false,
        locations: [],
      };
    }
  } catch (error) {
    console.error("Error in optimized app block detection:", error);
    throw new Error("Unable to check app block usage");
  }
}

// Optimized Page-Specific Detection - Reuses assets data
export async function checkPageSpecificInstallationsAccurate(
  shopDomain: string,
  themeId: string,
  admin: any,
  session: any,
  assets?: any[], // Optional: reuse assets from previous call
): Promise<PageStatus[]> {
  if (!admin) {
    return [];
  }

  try {
    // App block identifiers to search for
    const appBlockId =
      "shopify://apps/betterbundle/blocks/phoenix/0199379f-82d0-7b3b-9980-329260e4bf4b";
    const appBlockHandle = "phoenix";
    const appBlockClass = "shopify-app-block";

    // Get widget configuration for page settings
    const config = await getWidgetConfiguration(shopDomain);

    // Define page types and their corresponding template files (4 core pages only)
    const pageTypes = [
      {
        type: "product_page",
        templateFiles: [
          "templates/product.json",
          "sections/product-template.liquid",
          "sections/main-product.liquid",
        ],
        displayName: "Product Page",
      },
      {
        type: "homepage",
        templateFiles: ["templates/index.json", "sections/index.liquid"],
        displayName: "Homepage",
      },
      {
        type: "collection",
        templateFiles: [
          "templates/collection.json",
          "sections/collection-template.liquid",
        ],
        displayName: "Collection Page",
      },
      {
        type: "cart_page",
        templateFiles: ["templates/cart.json", "sections/cart-template.liquid"],
        displayName: "Cart Page",
      },
    ];

    const pageStatuses: PageStatus[] = [];

    // If assets not provided, fetch them once
    let themeAssets = assets;
    if (!themeAssets) {
      // Extract numeric theme ID from GraphQL ID
      const numericThemeId = themeId.replace(
        "gid://shopify/OnlineStoreTheme/",
        "",
      );

      const response = await fetch(
        `https://${shopDomain}/admin/api/2024-07/themes/${numericThemeId}/assets.json`,
        {
          headers: {
            "X-Shopify-Access-Token": session.accessToken,
            "Content-Type": "application/json",
          },
        },
      );

      if (response.ok) {
        const assetsData = await response.json();
        themeAssets = assetsData.assets || [];
      } else {
        console.error(`⚠️ Could not fetch assets: ${response.status}`);
        themeAssets = [];
      }
    }

    // Use the same GraphQL approach that successfully finds app blocks

    try {
      const graphqlQuery = `
        query getThemeTemplateFiles($themeId: ID!) {
          theme(id: $themeId) {
            files(filenames: ["templates/product.json", "templates/collection.json", "templates/index.json", "templates/cart.json"]) {
              nodes {
                filename
                body {
                  ... on OnlineStoreThemeFileBodyText {
                    content
                  }
                }
              }
            }
          }
        }
      `;

      const graphqlResponse = await fetch(
        `https://${shopDomain}/admin/api/2024-07/graphql.json`,
        {
          method: "POST",
          headers: {
            "X-Shopify-Access-Token": session.accessToken,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: graphqlQuery,
            variables: { themeId: themeId },
          }),
        },
      );

      if (graphqlResponse.ok) {
        const graphqlData = await graphqlResponse.json();

        if (graphqlData.errors) {
          console.error(
            "❌ GraphQL errors in page detection:",
            graphqlData.errors,
          );
        } else {
          const templateFiles = graphqlData.data?.theme?.files?.nodes || [];

          // Create a map of template files to their content for quick lookup
          const templateMap = new Map();
          for (const file of templateFiles) {
            if (file.body?.content) {
              templateMap.set(file.filename, file.body.content);
            }
          }

          // Check each page type using the GraphQL data
          for (const pageType of pageTypes) {
            const pageStatus: PageStatus = {
              pageType: pageType.type,
              isActive: false,
              templateFile: pageType.templateFiles[0], // Use first template file as primary
              configuration: {
                enabled:
                  getPageConfigValue(config, pageType.type, "enabled") || false,
                title:
                  getPageConfigValue(config, pageType.type, "title") ||
                  "You Might Also Like",
                limit: getPageConfigValue(config, pageType.type, "limit") || 6,
                showPrices:
                  getPageConfigValue(config, pageType.type, "showPrices") ||
                  true,
                showReasons:
                  getPageConfigValue(config, pageType.type, "showReasons") ||
                  true,
              },
            };

            // Check all template files for this page type
            for (const templateFile of pageType.templateFiles) {
              const content = templateMap.get(templateFile);

              if (content) {
                try {
                  // Handle both JSON and Liquid files
                  let hasAppBlock = false;
                  if (templateFile.endsWith(".json")) {
                    // Parse JSON and check for app blocks
                    const cleanContent = content.replace(
                      /\/\*[\s\S]*?\*\//g,
                      "",
                    );
                    const templateData = JSON.parse(cleanContent);
                    hasAppBlock = checkJsonForAppBlocks(
                      templateData,
                      appBlockId,
                    );
                  } else {
                    // For Liquid files, check for multiple identifiers
                    hasAppBlock =
                      content.includes(appBlockId) ||
                      content.includes(appBlockHandle) ||
                      content.includes(appBlockClass) ||
                      content.includes('data-block-handle="phoenix"') ||
                      content.includes("shopify-app-block") ||
                      content.includes("blocks.phoenix") ||
                      content.includes("render 'app-block'") ||
                      content.includes("phoenix-recommendations") ||
                      content.includes("Phoenix Smart Recommendations") ||
                      content.includes("phoenix-recommendations-grid") ||
                      content.includes("PhoenixRecommendations") ||
                      content.includes("PhoenixContextDetection") ||
                      content.includes("phoenix-recommendation-item") ||
                      content.includes(
                        "cdn.shopify.com/extensions/019938dd-10be-71dc-b84f-ad55193f5e51",
                      ) ||
                      content.includes("context-detection.js") ||
                      content.includes("recommendations.js") ||
                      content.includes("phoenix-recommendations.css") ||
                      content.includes("019938dd-10be-71dc-b84f-ad55193f5e51");
                  }

                  if (hasAppBlock) {
                    pageStatus.isActive = true;
                    pageStatus.sectionName = "phoenix";
                    pageStatus.templateFile = templateFile; // Update to the actual file found
                    break; // Found it, no need to check other template files
                  }
                } catch (parseError) {
                  console.error(
                    `⚠️ Could not parse ${templateFile}:`,
                    parseError,
                  );
                }
              }
            }

            pageStatuses.push(pageStatus);
          }
        }
      } else {
        // Fallback to empty page statuses
        for (const pageType of pageTypes) {
          pageStatuses.push({
            pageType: pageType.type,
            isActive: false,
            templateFile: pageType.templateFiles[0],
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
                getPageConfigValue(config, pageType.type, "showReasons") ||
                true,
            },
          });
        }
      }
    } catch (error) {
      console.error("❌ GraphQL error in page detection:", error);
      // Fallback to empty page statuses
      for (const pageType of pageTypes) {
        pageStatuses.push({
          pageType: pageType.type,
          isActive: false,
          templateFile: pageType.templateFiles[0],
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
        });
      }
    }

    return pageStatuses;
  } catch (error) {
    console.error("Error in optimized page-specific detection:", error);
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
