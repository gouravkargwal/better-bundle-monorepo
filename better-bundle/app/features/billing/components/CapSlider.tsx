import { RangeSlider, Text } from "@shopify/polaris";
import { CAP_STEP, MAX_CAP, MIN_CAP } from "../capBounds";

interface CapSliderProps {
  value: number;
  onChange: (value: number) => void;
  /** Share of attributed revenue charged, e.g. 0.03. */
  commissionRate: number;
  shopCurrency: string;
  label?: string;
  disabled?: boolean;
}

/**
 * Picks a spend cap, labelled in the units merchants actually think in.
 *
 * Nobody decides "my commission ceiling should be $50". They decide how much
 * of their sales they are happy for us to be involved in, so the help text
 * converts the cap back into the sales it covers.
 */
export function CapSlider({
  value,
  onChange,
  commissionRate,
  shopCurrency,
  label = "Monthly limit",
  disabled = false,
}: CapSliderProps) {
  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: shopCurrency,
      maximumFractionDigits: 0,
    }).format(amount);

  const salesCovered = commissionRate > 0 ? value / commissionRate : 0;

  return (
    <RangeSlider
      label={label}
      min={MIN_CAP}
      max={MAX_CAP}
      step={CAP_STEP}
      value={value}
      onChange={(next) => onChange(Number(next))}
      disabled={disabled}
      output
      helpText={`Covers roughly ${formatCurrency(
        salesCovered,
      )} of recommended sales per 30 days.`}
      prefix={<Text as="span">{formatCurrency(MIN_CAP)}</Text>}
      suffix={<Text as="span">{formatCurrency(value)}</Text>}
    />
  );
}
