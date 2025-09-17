import prisma from "../db.server";

export interface ExtensionStatus {
  extensions: {
    atlas: {
      name: string;
      type: "web_pixel";
      status: "active" | "inactive" | "not_installed";
      description: string;
      installation_url?: string;
      last_activity?: string;
    };
    venus: {
      name: string;
      type: "customer_account_ui";
      status: "active" | "inactive" | "not_installed";
      description: string;
      installation_url?: string;
      last_activity?: string;
    };
    phoenix: {
      name: string;
      type: "theme_extension";
      status: "active" | "inactive" | "not_installed";
      description: string;
      installation_url?: string;
      last_activity?: string;
    };
    apollo: {
      name: string;
      type: "post_purchase";
      status: "active" | "inactive" | "not_installed";
      description: string;
      installation_url?: string;
      last_activity?: string;
    };
  };
  pageStatuses: Array<{
    pageType: string;
    isActive: boolean;
    extensionType: string;
    lastSeen?: string;
  }>;
  overallStatus: "healthy" | "warning" | "critical";
}

export async function getExtensionStatus(
  shop: string,
): Promise<ExtensionStatus> {
  try {
    // Get real data from our analytics tables
    const [userSessions, userInteractions, purchaseAttributions] =
      await Promise.all([
        prisma.userSession.findMany({
          where: { shopId: shop },
          select: {
            extensionsUsed: true,
            createdAt: true,
            lastActive: true,
          },
          orderBy: { lastActive: "desc" },
          take: 100,
        }),
        prisma.userInteraction.findMany({
          where: { shopId: shop },
          select: {
            extensionType: true,
            createdAt: true,
          },
          orderBy: { createdAt: "desc" },
          take: 100,
        }),
        prisma.purchaseAttribution.findMany({
          where: { shopId: shop },
          select: {
            contributingExtensions: true,
            createdAt: true,
          },
          orderBy: { createdAt: "desc" },
          take: 50,
        }),
      ]);

    // Analyze extension activity
    const extensionActivity = {
      atlas: {
        sessions: 0,
        interactions: 0,
        purchases: 0,
        lastActivity: null as Date | null,
      },
      venus: {
        sessions: 0,
        interactions: 0,
        purchases: 0,
        lastActivity: null as Date | null,
      },
      phoenix: {
        sessions: 0,
        interactions: 0,
        purchases: 0,
        lastActivity: null as Date | null,
      },
      apollo: {
        sessions: 0,
        interactions: 0,
        purchases: 0,
        lastActivity: null as Date | null,
      },
    };

    // Count sessions by extension
    userSessions.forEach((session) => {
      // Extract extension types from extensionsUsed JSON field
      if (
        session.extensionsUsed &&
        typeof session.extensionsUsed === "object"
      ) {
        const extensions = session.extensionsUsed as Record<string, any>;
        Object.keys(extensions).forEach((extType) => {
          if (extensionActivity[extType as keyof typeof extensionActivity]) {
            extensionActivity[extType as keyof typeof extensionActivity]
              .sessions++;
            if (
              !extensionActivity[extType as keyof typeof extensionActivity]
                .lastActivity ||
              session.lastActive >
                extensionActivity[extType as keyof typeof extensionActivity]
                  .lastActivity!
            ) {
              extensionActivity[
                extType as keyof typeof extensionActivity
              ].lastActivity = session.lastActive;
            }
          }
        });
      }
    });

    // Count interactions by extension
    userInteractions.forEach((interaction) => {
      if (
        interaction.extensionType &&
        extensionActivity[
          interaction.extensionType as keyof typeof extensionActivity
        ]
      ) {
        extensionActivity[
          interaction.extensionType as keyof typeof extensionActivity
        ].interactions++;
        if (
          !extensionActivity[
            interaction.extensionType as keyof typeof extensionActivity
          ].lastActivity ||
          interaction.createdAt >
            extensionActivity[
              interaction.extensionType as keyof typeof extensionActivity
            ].lastActivity!
        ) {
          extensionActivity[
            interaction.extensionType as keyof typeof extensionActivity
          ].lastActivity = interaction.createdAt;
        }
      }
    });

    // Count purchases by extension
    purchaseAttributions.forEach((attribution) => {
      // Extract extension types from contributingExtensions JSON field
      if (
        attribution.contributingExtensions &&
        typeof attribution.contributingExtensions === "object"
      ) {
        const extensions = attribution.contributingExtensions as Record<
          string,
          any
        >;
        Object.keys(extensions).forEach((extType) => {
          if (extensionActivity[extType as keyof typeof extensionActivity]) {
            extensionActivity[extType as keyof typeof extensionActivity]
              .purchases++;
            if (
              !extensionActivity[extType as keyof typeof extensionActivity]
                .lastActivity ||
              attribution.createdAt >
                extensionActivity[extType as keyof typeof extensionActivity]
                  .lastActivity!
            ) {
              extensionActivity[
                extType as keyof typeof extensionActivity
              ].lastActivity = attribution.createdAt;
            }
          }
        });
      }
    });

    // Determine extension status based on activity
    const getExtensionStatus = (
      extensionName: keyof typeof extensionActivity,
    ) => {
      const activity = extensionActivity[extensionName];
      const hasRecentActivity =
        activity.lastActivity &&
        Date.now() - activity.lastActivity.getTime() < 7 * 24 * 60 * 60 * 1000; // 7 days

      if (activity.sessions > 0 || activity.interactions > 0) {
        return hasRecentActivity ? "active" : "inactive";
      }
      return "not_installed";
    };

    // Build page statuses based on extension activity
    const pageStatuses = [
      {
        pageType: "product_page",
        isActive:
          extensionActivity.atlas.sessions > 0 ||
          extensionActivity.phoenix.sessions > 0,
        extensionType:
          extensionActivity.atlas.sessions > extensionActivity.phoenix.sessions
            ? "atlas"
            : "phoenix",
        lastSeen:
          extensionActivity.atlas.lastActivity?.toISOString() ||
          extensionActivity.phoenix.lastActivity?.toISOString(),
      },
      {
        pageType: "homepage",
        isActive: extensionActivity.atlas.sessions > 0,
        extensionType: "atlas",
        lastSeen: extensionActivity.atlas.lastActivity?.toISOString(),
      },
      {
        pageType: "collection",
        isActive: extensionActivity.atlas.sessions > 0,
        extensionType: "atlas",
        lastSeen: extensionActivity.atlas.lastActivity?.toISOString(),
      },
      {
        pageType: "cart_page",
        isActive: extensionActivity.phoenix.sessions > 0,
        extensionType: "phoenix",
        lastSeen: extensionActivity.phoenix.lastActivity?.toISOString(),
      },
      {
        pageType: "customer_account",
        isActive: extensionActivity.venus.sessions > 0,
        extensionType: "venus",
        lastSeen: extensionActivity.venus.lastActivity?.toISOString(),
      },
      {
        pageType: "post_purchase",
        isActive: extensionActivity.apollo.sessions > 0,
        extensionType: "apollo",
        lastSeen: extensionActivity.apollo.lastActivity?.toISOString(),
      },
    ];

    // Determine overall status
    const activeExtensions = Object.values(extensionActivity).filter(
      (ext) => ext.sessions > 0 || ext.interactions > 0,
    ).length;

    let overallStatus: "healthy" | "warning" | "critical";
    if (activeExtensions >= 3) {
      overallStatus = "healthy";
    } else if (activeExtensions >= 1) {
      overallStatus = "warning";
    } else {
      overallStatus = "critical";
    }

    return {
      extensions: {
        atlas: {
          name: "Atlas (Web Pixels)",
          type: "web_pixel",
          status: getExtensionStatus("atlas"),
          description:
            "Tracks customer behavior across your store using Shopify Web Pixels",
          installation_url: `/admin/apps/better-bundle/extensions/atlas`,
          last_activity: extensionActivity.atlas.lastActivity?.toISOString(),
        },
        venus: {
          name: "Venus (Customer Account)",
          type: "customer_account_ui",
          status: getExtensionStatus("venus"),
          description:
            "Shows personalized recommendations in customer account pages",
          installation_url: `/admin/apps/better-bundle/extensions/venus`,
          last_activity: extensionActivity.venus.lastActivity?.toISOString(),
        },
        phoenix: {
          name: "Phoenix (Theme Extension)",
          type: "theme_extension",
          status: getExtensionStatus("phoenix"),
          description: "Adds recommendation widgets to your theme pages",
          installation_url: `/admin/apps/better-bundle/extensions/phoenix`,
          last_activity: extensionActivity.phoenix.lastActivity?.toISOString(),
        },
        apollo: {
          name: "Apollo (Post-Purchase)",
          type: "post_purchase",
          status: getExtensionStatus("apollo"),
          description: "Shows upsell recommendations after purchase completion",
          installation_url: `/admin/apps/better-bundle/extensions/apollo`,
          last_activity: extensionActivity.apollo.lastActivity?.toISOString(),
        },
      },
      pageStatuses,
      overallStatus,
    };
  } catch (error) {
    console.error("Error getting extension status:", error);
    throw new Error("Failed to fetch extension status");
  }
}

export async function installExtension(
  shop: string,
  extensionType: string,
): Promise<{ success: boolean; message: string }> {
  try {
    // This would integrate with Shopify's extension installation API
    // For now, we'll return a success message with instructions

    const extensionInfo = {
      atlas: {
        name: "Atlas Web Pixel",
        instructions:
          "Web pixels are automatically installed when the app is installed. No additional setup required.",
      },
      venus: {
        name: "Venus Customer Account Extension",
        instructions:
          "Navigate to your app settings to enable customer account extensions.",
      },
      phoenix: {
        name: "Phoenix Theme Extension",
        instructions:
          "Add the theme extension to your store theme through the theme editor.",
      },
      apollo: {
        name: "Apollo Post-Purchase Extension",
        instructions:
          "Enable post-purchase extensions in your checkout settings.",
      },
    };

    const info = extensionInfo[extensionType as keyof typeof extensionInfo];

    if (!info) {
      return { success: false, message: "Unknown extension type" };
    }

    return {
      success: true,
      message: `${info.name} installation instructions: ${info.instructions}`,
    };
  } catch (error) {
    console.error("Error installing extension:", error);
    return { success: false, message: "Failed to install extension" };
  }
}
