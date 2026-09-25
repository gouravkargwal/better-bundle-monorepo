# BetterBundle — App Store listing

Source: 1★/2★ reviews of ReConvert (4.8, 3,093 reviews), Rebuy (4.8, 745), Wiser, LimeSpot,
pulled 2026-09-25. Pricing figures from `billing.service.ts` defaults.

---

## The finding

All four market leaders share the same #1 complaint, in merchants' own words:

| App | Complaint |
|---|---|
| Wiser | charges "a percentage share of ALL sales on our site, not just attributed to what Wiser's recommendations were able to help sell" — *"why isn't billing based off that?"* |
| LimeSpot | "This app charged you based on the total revenue of your store NOT the revenue from THIS APP" / "they seem to take credit for selling things which have nothing to do with them" |
| ReConvert | "charges based on total store orders regardless of whether upsells were used or displayed" |
| Rebuy | "overcharged us several thousand dollars"; "300+ euros a month" for features that didn't work |

**Merchants in this category are not angry about recommendations. They are angry about the bill.**
BetterBundle's billing model is a literal answer to the most common grievance in the category.
That is the listing. Everything else is supporting detail.

Secondary complaints worth naming in copy:

- **Third-party ads injected into checkout** — ReConvert ("affiliate offers on checkout pages
  without your consent") and Rebuy ("3rd party adverts" instead of the merchant's own offers).
- **Breaking the cart / leftover code on uninstall** — Rebuy (one merchant claims $25k lost),
  LimeSpot (silently disconnected from stores).
- **Setup complexity** — Rebuy's "data sources, boolean operators, logic trees" learning curve.
- **Support is bots, or absent.**

---

## Positioning

> Every other recommendation app bills you for sales it didn't make. We only bill for the ones we did —
> and we show you the receipts.

---

## Listing fields

Verify current character limits in the Partner Dashboard before pasting; these are the limits as of
the last listing spec I know (name 30, subtitle 62, intro 100, details 500, features 5 × 80).

### App name (30)
```
BetterBundle ‑ Upsell AI
```

### App card subtitle (62)
```
AI product recommendations. Pay only on revenue we generate.
```

### App introduction (100)
```
Recommendations on product, post-purchase and thank-you pages — billed only on sales we drive.
```

### App details (500)
```
Most recommendation apps bill you on your store's total revenue, whether or not the app sold
anything. BetterBundle doesn't.

We track every sale our recommendations actually cause, show you the exact order behind each one,
and charge 3% of only that. Never your other sales.

You pay nothing until we've earned you $1,000 across 30 separate orders — enough that you can
see it working, not just one lucky sale. After that your bill is capped at $29/month, no matter
how much we sell for you. No usage tiers, no surprise upgrades.

No third-party ads in your checkout. Only your products.
```

### Feature bullets (5 × 80)
```
1. Billed only on revenue we're proven to generate — never on your total sales
2. Free until we've made you $1,000 across 30 orders. Then 3%, capped at $29/mo
3. Every charge traceable to the exact order and recommendation that caused it
4. Recommendations on product pages, post-purchase, and the thank-you page
5. No third-party ads or affiliate offers — we only ever show your products
```

### Search terms
```
frequently bought together, product recommendations, post purchase upsell,
thank you page upsell, cross sell, related products, cart upsell, increase AOV,
product bundles, personalized recommendations
```

### Pricing plan (Partner Dashboard)
Name the plan so the cap is visible before install — this is the conversion moment.
```
Plan name:  Pay as you sell
Price:      Free to install
Details:    • $0 until we generate $1,000 across 30 separate orders
            • Then 3% of revenue we're proven to have generated
            • Hard cap of $29/month, whatever your store size
            • Refunds deducted from attributed revenue
              ⚠️ DO NOT SHIP THIS LINE until the refund gap is fixed —
              see finding 1 in the attribution audit. It is currently false.
```

---

## Screenshots

Lead with the receipt, not the widget. Every competitor leads with widget screenshots; none of them
can show this, because showing it would expose what they're charging for.

1. **ProofPage** — attributed revenue with order-level line items. Your whole differentiator.
2. **Billing screen** — the $29 cap and current cycle usage, visible.
3. Product page recommendations in a real theme.
4. Post-purchase offer.
5. Thank-you page recommendations.

---

## Two risks

**1. Attribution disputes are how you become the next 1★ review.** Wiser and LimeSpot both bill on
some notion of attribution and merchants still call it a scam, because they don't believe the
numbers. Your defence is the ProofPage: order ID, which recommendation, what window, and
conservative defaults. If a sale is ambiguous, don't claim it. Under-claiming costs you cents and
buys the review.

**2. The $29 cap is a great door and a bad ceiling.** 3% capped at $29 means the cap binds at ~$967
attributed revenue/month. A merchant you make $50k/month for pays you $29. Fine for launch —
it's the sharpest acquisition weapon in the category — but you need a plan for caps that scale with
store size before you have merchants worth keeping. Changing it later on existing merchants is
painful, so decide now whether v1 launches with a single $29 cap or a small tier ladder.
