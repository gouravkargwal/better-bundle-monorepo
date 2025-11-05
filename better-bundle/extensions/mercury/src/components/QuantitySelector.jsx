/**
 * Quantity selector component with increment/decrement buttons
 */
export function QuantitySelector({
  productId,
  quantity,
  onDecrement,
  onIncrement,
  disabled,
}) {
  return (
    <s-stack direction="inline" gap="small-100" alignItems="center">
      <s-button onClick={onDecrement} disabled={disabled || quantity <= 1}>
        <s-icon type="minus" />
      </s-button>
      <s-text>{quantity}</s-text>
      <s-button onClick={onIncrement} disabled={disabled || quantity >= 10}>
        <s-icon type="plus" />
      </s-button>
    </s-stack>
  );
}
