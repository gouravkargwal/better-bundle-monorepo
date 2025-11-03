export function getProductImages(product) {
  if (!product.images || product.images.length === 0) {
    if (product.image?.url) {
      return [{ url: product.image.url }];
    }
    return [];
  }
  return product.images;
}

export function getOptionValueFromVariant(variant, optionName, product) {
  const option = product.options?.find((opt) => opt.name === optionName);
  if (!option) return null;
  const title = variant.title || "";
  const parts = title.split(" / ");
  const optionIndex = option.position - 1;
  return parts[optionIndex] || null;
}

export function getAvailableOptions(product, selectedOptions = {}) {
  if (!product.options || !product.variants) return product.options || [];
  return product.options.map((option) => {
    const availableValues = new Set();
    const matchingVariants = product.variants.filter((variant) => {
      return Object.keys(selectedOptions).every((optionName) => {
        if (optionName === option.name) return true;
        const selectedValue = selectedOptions[optionName];
        return variant.title && variant.title.includes(selectedValue);
      });
    });
    matchingVariants.forEach((variant) => {
      if (variant.inventory > 0) {
        const optionValue = getOptionValueFromVariant(
          variant,
          option.name,
          product,
        );
        if (optionValue) {
          availableValues.add(optionValue);
        }
      }
    });
    return {
      ...option,
      values: option.values.filter((value) => availableValues.has(value)),
    };
  });
}

export function getSelectedVariant(product, selectedVariants) {
  const selected = selectedVariants[product.id];

  if (!selected || Object.keys(selected).length === 0 || !product.variants) {
    const firstAvailableVariant = product.variants?.find(
      (variant) => variant.inventory > 0,
    );
    return (
      product.selectedVariantId ||
      (firstAvailableVariant ? firstAvailableVariant.id : null) ||
      (product.variants && product.variants.length > 0
        ? product.variants[0].id
        : null)
    );
  }

  const requiredOptions = product.options || [];
  const allOptionsSelected = requiredOptions.every((option) => {
    return selected[option.name] && selected[option.name] !== "";
  });

  if (!allOptionsSelected) {
    const firstAvailableVariant = product.variants?.find(
      (variant) => variant.inventory > 0,
    );
    return firstAvailableVariant
      ? firstAvailableVariant.id
      : product.variants && product.variants.length > 0
        ? product.variants[0].id
        : null;
  }

  const matchingVariant = product.variants.find((variant) => {
    return Object.keys(selected).every((optionName) => {
      const optionValue = selected[optionName];
      return variant.title && variant.title.includes(optionValue);
    });
  });

  return matchingVariant ? matchingVariant.id : product.selectedVariantId;
}

export function hasValidVariantSelected(product, selectedVariants) {
  const variantId = getSelectedVariant(product, selectedVariants);
  if (!variantId || !product.variants) return false;

  const selected = selectedVariants[product.id] || {};
  const requiredOptions = product.options || [];
  const allOptionsSelected = requiredOptions.every((option) => {
    return selected[option.name] && selected[option.name] !== "";
  });

  return requiredOptions.length === 0 || allOptionsSelected;
}

export function isVariantInStock(product, selectedVariants) {
  const selectedVariantId = getSelectedVariant(product, selectedVariants);
  if (!selectedVariantId || !product.variants) return true;
  const variant = product.variants.find((v) => v.id === selectedVariantId);
  return variant ? variant.inventory > 0 : true;
}

export function getPrimaryImageUrl(product, selectedImageIndex) {
  const images = getProductImages(product);
  if (images.length === 0) {
    return null;
  }

  const index = selectedImageIndex?.[product.id] ?? 0;
  const selectedImage = images[index];
  const fallbackImage = images[0];
  const imageUrl = selectedImage?.url || fallbackImage?.url || null;

  return imageUrl;
}
