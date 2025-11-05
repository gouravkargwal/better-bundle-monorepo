/**
 * Collapsible product image gallery component
 */
export function ProductImageGallery({
  product,
  images,
  selectedImageIndex,
  expanded,
  onImageSelect,
  onToggle,
}) {
  if (!images || images.length <= 1) {
    return null;
  }

  const currentIndex = selectedImageIndex?.[product.id] ?? 0;
  const currentImage = images[currentIndex];

  return (
    <s-details open={expanded} onToggle={onToggle}>
      <s-summary>
        <s-text>View all {images.length} images</s-text>
      </s-summary>

      {/* Gallery Content */}
      <s-box padding="base" background="subdued" borderRadius="base">
        {/* Current Image */}
        <s-box paddingBlockEnd="base">
          <s-image
            src={currentImage?.url || ""}
            alt={`${product.title} - Image ${currentIndex + 1}`}
            aspectRatio="4/3"
            inlineSize="fill"
            borderRadius="base"
            objectFit="cover"
          />
        </s-box>

        {/* Image Counter */}
        <s-box paddingBlockEnd="base">
          <s-text type="small" color="subdued">
            {currentIndex + 1} of {images.length}
          </s-text>
        </s-box>

        {/* Thumbnails */}
        <s-stack direction="inline" gap="small-100" justifyContent="center">
          {images.map((image, index) => (
            <s-clickable
              key={index}
              onClick={() => onImageSelect(product.id, index)}
              accessibilityLabel={`View image ${index + 1}`}
            >
              <s-box
                inlineSize="50px"
                blockSize="50px"
                border={currentIndex === index ? "base" : "none"}
                borderWidth={currentIndex === index ? "base" : "none"}
                borderRadius="small"
                overflow="hidden"
                padding="none"
              >
                <s-image
                  src={image.url || ""}
                  alt={`Thumbnail ${index + 1}`}
                  aspectRatio="1/1"
                  objectFit="cover"
                />
              </s-box>
            </s-clickable>
          ))}
        </s-stack>
      </s-box>
    </s-details>
  );
}
