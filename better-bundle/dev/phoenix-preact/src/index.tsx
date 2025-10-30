import { render } from "preact";
import type { FunctionalComponent } from "preact";
import { Carousel } from "./components/Carousel";
import "./style.css";

// App Component
const App: FunctionalComponent<{
  type: string;
  settings: Record<string, unknown>;
  shopify: Record<string, unknown>;
}> = ({ type, settings, shopify }) => {
  const s = settings as Record<string, string | number | boolean | undefined>;
  const sh = shopify as Record<string, string | number | boolean | undefined>;

  if (type === "product-carousel") {
    return (
      <div className="phoenix-extension">
        <Carousel
          productIds={
            (s.product_ids as any) ||
            (sh.productId ? [sh.productId as any] : [])
          }
          customerId={sh.customerId as string | undefined}
          shopDomain={String(sh.shop || "")}
          limit={Number(s.limit ?? 6)}
          context={(s.context as any) || "product_page"}
          enableAutoplay={Boolean(s.enable_autoplay)}
          autoplayDelay={Number(s.autoplay_delay ?? 2500)}
          showArrows={Boolean(s.show_arrows)}
          showPagination={Boolean(s.show_pagination)}
          currency={String(s.currency || "USD")}
        />
      </div>
    );
  }

  if (type === "test-component") {
    return (
      <div
        style={{
          padding: "20px",
          backgroundColor: String(s.background_color || "#f0f0f0"),
          color: String(s.primary_color || "#333"),
          borderRadius: "8px",
          border: "2px solid #007acc",
        }}
      >
        <h3>{String(s.title || "Phoenix Test Component")}</h3>
        <p>
          Preact is working with hot reload! Updated{" "}
          {new Date().toLocaleTimeString()}
        </p>
        <p>Product ID: {String(sh.productId || "None")}</p>
        <div style={{ fontSize: "12px", marginTop: "10px" }}>
          <strong>Settings:</strong> {JSON.stringify(s, null, 2)}
        </div>
      </div>
    );
  }

  return (
    <div className="phoenix-component-error">
      <h3>Component "{type}" not found</h3>
      <p>Available: product-carousel, test-component</p>
    </div>
  );
};

// Initialization Logic
const initializePhoenixComponents = () => {
  console.log("Phoenix Extension: Checking for components...");

  // Find all Phoenix extension containers
  const containers = document.querySelectorAll("[data-phoenix-component]");
  console.log(
    `Phoenix Extension: Found ${containers.length} components to mount`,
  );

  if (containers.length === 0) {
    console.log("Phoenix Extension: No components found, waiting for DOM...");
    return false;
  }

  containers.forEach((container, index) => {
    try {
      const componentType = container.getAttribute("data-phoenix-component");
      const propsData = container.getAttribute("data-phoenix-props");

      if (!componentType) {
        console.warn(
          "Phoenix Extension: Missing component type on container",
          container,
        );
        return;
      }

      const props = propsData ? JSON.parse(propsData) : {};

      const shopifyContext = {
        productId: container.getAttribute("data-product-id"),
        collectionId: container.getAttribute("data-collection-id"),
        customerId: (window as any).meta?.customer?.id,
        shop: (window as any).Shopify?.shop,
      };

      console.log(
        `Phoenix Extension: Mounting ${componentType} component #${index}`,
        { props, shopifyContext },
      );

      // Check if container is valid before rendering
      if (container && container.nodeType === Node.ELEMENT_NODE) {
        render(
          <App
            type={componentType}
            settings={props}
            shopify={shopifyContext}
          />,
          container as Element,
        );
      } else {
        console.error(
          "Phoenix Extension: Invalid container element",
          container,
        );
      }
    } catch (error) {
      console.error("Phoenix Extension: Failed to mount component", error);
    }
  });

  return true;
};

// Multiple initialization strategies
const tryInitialization = () => {
  if (initializePhoenixComponents()) {
    console.log("Phoenix Extension: Successfully initialized");
    return;
  }

  // Retry after a small delay if no components found
  setTimeout(() => {
    if (initializePhoenixComponents()) {
      console.log("Phoenix Extension: Successfully initialized (delayed)");
    } else {
      console.log("Phoenix Extension: No components found after retry");
    }
  }, 100);
};

// Try different DOM ready strategies
if (document.readyState === "loading") {
  // DOM is still loading
  document.addEventListener("DOMContentLoaded", tryInitialization);
} else if (
  document.readyState === "interactive" ||
  document.readyState === "complete"
) {
  // DOM is already ready
  tryInitialization();
}

// Also listen for page load as fallback
window.addEventListener("load", () => {
  // Only initialize if we haven't already
  const containers = document.querySelectorAll("[data-phoenix-component]");
  if (containers.length > 0) {
    // Check if any containers are empty (not yet mounted)
    const emptyContainers = Array.from(containers).filter(
      (container) =>
        !container.querySelector(
          ".phoenix-extension, .phoenix-component-error",
        ),
    );

    if (emptyContainers.length > 0) {
      console.log(
        "Phoenix Extension: Found unmounted components, initializing...",
      );
      tryInitialization();
    }
  }
});
