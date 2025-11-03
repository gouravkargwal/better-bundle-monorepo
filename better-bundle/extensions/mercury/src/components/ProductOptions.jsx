/**
 * Product variant options selector component
 */
export function ProductOptions({
  options,
  productId,
  selectedOptions,
  onOptionChange,
}) {
  if (!options || options.length === 0) {
    return <s-box></s-box>; // Apply prop for consistent empty state
  }

  return (
    <s-stack direction="inline" gap="small-200">
      {options.map((option) => (
        <s-box
          key={option.id}
          inlineSize={options.length === 2 ? "48%" : "33%"}
          minInlineSize="0"
        >
          <s-select
            label={option.name}
            value={selectedOptions?.[option.name] || ""}
            onChange={(e) => {
              const value =
                e.currentTarget && "value" in e.currentTarget
                  ? e.currentTarget.value
                  : "";
              onOptionChange(productId, option.name, value);
            }}
          >
            <s-option value="">Select</s-option>
            {option.values.map((value) => (
              <s-option key={value} value={value}>
                {value}
              </s-option>
            ))}
          </s-select>
        </s-box>
      ))}
    </s-stack>
  );
}
