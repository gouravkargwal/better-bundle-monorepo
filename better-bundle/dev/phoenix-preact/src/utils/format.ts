export function formatPrice(amount: number, currency: string) {
  const zeroFrac = currency === "JPY" || currency === "KRW";
  const fmt = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: zeroFrac ? 0 : 2,
    maximumFractionDigits: zeroFrac ? 0 : 2,
  });
  let out = fmt.format(amount);
  if (currency === "INR") out = out.replace("₹", "Rs. ");
  return out;
}


