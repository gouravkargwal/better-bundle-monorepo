/**
 * Theme Editor Deep Linking Utilities
 * Common functions for opening Shopify Theme Editor with app blocks
 */

// App configuration
const APP_CONFIG = {
  apiKey: "87c44f5966daa80691a480bcd03c225c",
  blockHandle: "phoenix",
} as const;

/**
 * Opens the Shopify Theme Editor with the Phoenix widget
 * @param shopDomain - The shop's domain (e.g., "myshop.myshopify.com")
 * @param options - Configuration options for the deep link
 */
export function openThemeEditor(
  shopDomain: string,
  options: {
    template?: string;
    target?: string;
    action?: "add" | "edit";
  } = {},
) {
  if (!shopDomain) {
    console.error("Missing shop domain for theme editor.");
    return;
  }

  const {
    template = "product",
    target = "newAppsSection",
    action = "add",
  } = options;

  // Construct the deep-link URL to the Shopify Theme Editor
  let url: string;

  if (action === "add") {
    // For adding new widget - shows "Add Section" menu with widget highlighted
    url = `https://${shopDomain}/admin/themes/current/editor?template=${template}&addAppBlockId=${APP_CONFIG.apiKey}/${APP_CONFIG.blockHandle}&target=${target}`;
  } else {
    // For editing existing widget - scrolls to and selects widget's settings
    url = `https://${shopDomain}/admin/themes/current/editor?template=${template}&section=${APP_CONFIG.apiKey}-${APP_CONFIG.blockHandle}`;
  }

  console.log("Redirecting to theme editor:", url);
  console.log(`Action: ${action}, Template: ${template}, Target: ${target}`);

  // Create a temporary link element and click it to open in new tab
  // This avoids popup blockers since it's a direct user action
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Opens theme editor for adding the Phoenix widget (installation)
 */
export function openThemeEditorForInstall(
  shopDomain: string,
  template: string = "product",
) {
  openThemeEditor(shopDomain, {
    template,
    target: "newAppsSection",
    action: "add",
  });
}

/**
 * Opens theme editor for previewing/editing the Phoenix widget
 */
export function openThemeEditorForPreview(shopDomain: string) {
  openThemeEditor(shopDomain, {
    template: "product",
    target: "newAppsSection",
    action: "add", // This will show the widget if installed, or guide to add if not
  });
}
