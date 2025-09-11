import {
  Card,
  BlockStack,
  Text,
  Button,
  InlineStack,
  Box,
  InlineGrid,
  SkeletonBodyText,
  SkeletonDisplayText,
  Modal,
  RangeSlider,
} from "@shopify/polaris";
import { useState } from "react";
import { openThemeEditorForPreview } from "../../utils/theme-editor";

interface WidgetPreviewSectionProps {
  selectedPageType: string;
  pageConfigs: Array<{
    key: string;
    label: string;
    title: string;
  }>;
  shopDomain?: string;
}

export function WidgetPreviewSection({
  selectedPageType,
  pageConfigs,
  shopDomain,
}: WidgetPreviewSectionProps) {
  const [previewModal, setPreviewModal] = useState<{
    open: boolean;
    pageType: string;
  }>({
    open: false,
    pageType: "",
  });
  const [previewProductCount, setPreviewProductCount] = useState(3);

  const getPageConfig = (pageType: string) => {
    return pageConfigs.find((page) => page.key === pageType);
  };

  const handleThemeEditorPreview = () => {
    if (!shopDomain) {
      console.error("Missing shop domain for preview.");
      return;
    }

    openThemeEditorForPreview(shopDomain);
  };

  const SkeletonProductCard = () => (
    <Box background="bg-surface" padding="300" borderRadius="200" shadow="100">
      <Box background="bg-surface-secondary" borderRadius="200" padding="0">
        <div style={{ height: "100px", marginBottom: "12px" }} />
      </Box>
      <BlockStack gap="100">
        <SkeletonBodyText lines={1} />
        <SkeletonBodyText lines={1} />
        <div style={{ width: "50px", height: "16px" }}>
          <SkeletonBodyText lines={1} />
        </div>
      </BlockStack>
    </Box>
  );

  return (
    <>
      <Card>
        <BlockStack gap="400">
          <InlineStack align="space-between">
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                👀 Preview
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                See how your recommendations will look to customers. Use the
                mockup preview to see a general idea, or preview on your live
                theme if you've already installed the widget.
              </Text>
            </BlockStack>
            <InlineStack gap="200">
              <Button
                variant="secondary"
                onClick={() =>
                  setPreviewModal({
                    open: true,
                    pageType: selectedPageType || "product_page",
                  })
                }
              >
                Preview Mockup
              </Button>
              <Button
                variant="primary"
                onClick={handleThemeEditorPreview}
                disabled={!shopDomain}
              >
                Preview & Install Widget
              </Button>
            </InlineStack>
          </InlineStack>

          {!shopDomain && (
            <Box
              background="bg-surface-warning"
              padding="300"
              borderRadius="200"
            >
              <Text as="p" variant="bodySm" tone="subdued">
                💡 <strong>Note:</strong> Shop domain is required to open the
                theme editor.
              </Text>
            </Box>
          )}
        </BlockStack>
      </Card>

      {/* Preview Modal */}
      <Modal
        open={previewModal.open}
        onClose={() => setPreviewModal({ open: false, pageType: "" })}
        title={`Preview: ${getPageConfig(previewModal.pageType)?.label || "Recommendations"}`}
        size="large"
      >
        <Modal.Section>
          <BlockStack gap="400">
            <Text as="p" variant="bodyMd" tone="subdued">
              This is how your recommendations will appear to customers. Adjust
              the slider to see different numbers of products.
            </Text>

            <Box>
              <Text as="p" variant="bodyMd" fontWeight="semibold">
                Number of products to show: {previewProductCount}
              </Text>
              <RangeSlider
                label=""
                min={1}
                max={5}
                step={1}
                value={previewProductCount}
                onChange={(value) =>
                  setPreviewProductCount(
                    typeof value === "number"
                      ? value
                      : parseInt(value.toString()),
                  )
                }
              />
            </Box>

            <Box
              background="bg-surface-secondary"
              padding="500"
              borderRadius="400"
            >
              <BlockStack gap="400">
                <SkeletonDisplayText size="medium" />

                <InlineGrid
                  columns={previewProductCount <= 2 ? 2 : 3}
                  gap="300"
                >
                  {Array.from({ length: previewProductCount }).map(
                    (_, index) => (
                      <SkeletonProductCard key={index} />
                    ),
                  )}
                </InlineGrid>
              </BlockStack>
            </Box>

            <Box background="bg-surface-brand" padding="300" borderRadius="200">
              <Text as="p" variant="bodySm" tone="subdued">
                💡 <strong>Note:</strong> The actual number of recommendations
                will be determined by your AI model based on available data and
                user context.
              </Text>
            </Box>
          </BlockStack>
        </Modal.Section>
      </Modal>
    </>
  );
}
