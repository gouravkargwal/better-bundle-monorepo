import type { LoaderFunctionArgs, MetaFunction } from "@remix-run/node";
import { json, redirect } from "@remix-run/node";

export const meta: MetaFunction = () => [
  { title: "BetterBundle — AI recommendations for Shopify" },
  {
    name: "description",
    content:
      "AI-powered recommendations that increase order value and repeat purchases on your Shopify store. Free until we've driven 30 sales.",
  },
];

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const url = new URL(request.url);

  if (url.searchParams.get("shop")) {
    throw redirect(`/app?${url.searchParams.toString()}`);
  }

  if (url.hostname.startsWith("app.") && url.pathname === "/") {
    throw redirect("/app");
  }

  return json({});
};

const BENEFITS = [
  {
    emoji: "💰",
    headline: "Higher order value",
    body: "Recommend complementary products at the exact moment of decision.",
  },
  {
    emoji: "🔁",
    headline: "More repeat purchases",
    body: "Bring customers back with products they didn't know you had.",
  },
  {
    emoji: "📈",
    headline: "Real revenue lift",
    body: "Control-group testing proves how much revenue we actually add.",
  },
  {
    emoji: "⚡",
    headline: "Zero effort",
    body: "One install. Add blocks in Shopify's editors — no code required.",
  },
] as const;

const FAQ_ITEMS = [
  {
    question: "How much will this cost me?",
    answer:
      "Nothing until we've driven 30 sales and $1,000 in attributed revenue. After that, 3% of the revenue we bring in. You set a cap — we never charge more.",
  },
  {
    question: "What does 'attributed' mean?",
    answer:
      "An order where a shopper saw one of our recommendations and bought. We log every attributed sale so you can audit it in your dashboard.",
  },
  {
    question: "Will this slow down my store?",
    answer:
      "No. Recommendations load in milliseconds. There's no per-shopper AI call, no external API, no slowdown.",
  },
  {
    question: "Does it work on my theme?",
    answer:
      "Yes. BetterBundle installs as a Shopify app. You add blocks in Shopify's theme, checkout, and account editors — no code required.",
  },
  {
    question: "What if it doesn't work for my store?",
    answer:
      "You don't pay. If we can't drive 30 sales and $1,000 in attributed revenue, you owe us nothing. Cancel anytime from your Shopify admin.",
  },
] as const;

const COLORS = {
  background: "#ffffff",
  bodyText: "#0f172a",
  mutedText: "#475569",
  cardBackground: "#f8fafc",
  divider: "#e2e8f0",
  ctaStart: "#667eea",
  ctaEnd: "#764ba2",
  success: "#059669",
  ctaText: "#ffffff",
} as const;

const FONT_STACK =
  'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

export default function MarketingIndex() {
  return (
    <>
      <style>{`
        details > summary {
          cursor: pointer;
          list-style: none;
        }
        details > summary::-webkit-details-marker {
          display: none;
        }
        details[open] > summary {
          margin-bottom: 12px;
        }
      `}</style>
      <div
        style={{
          minHeight: "100vh",
          fontFamily: FONT_STACK,
          color: COLORS.bodyText,
          background: COLORS.background,
        }}
      >
        {/* Wordmark */}
        <header
          style={{
            padding: "24px",
            maxWidth: "1080px",
            margin: "0 auto",
          }}
        >
          <div
            style={{
              fontSize: "20px",
              fontWeight: "700",
              color: COLORS.bodyText,
            }}
          >
            BetterBundle
          </div>
        </header>

        {/* Hero */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "800px",
              margin: "0 auto",
              textAlign: "center",
            }}
          >
            <h1
              style={{
                fontSize: "clamp(36px, 6vw, 56px)",
                fontWeight: "700",
                lineHeight: "1.1",
                marginBottom: "24px",
                color: COLORS.bodyText,
              }}
            >
              Turn your store into a personalized shopping experience.
            </h1>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 20px)",
                lineHeight: "1.6",
                color: COLORS.mutedText,
                marginBottom: "32px",
              }}
            >
              AI-powered recommendations that increase order value and repeat
              purchases. Live on your store in minutes.
            </p>
            <a
              href="/auth/login"
              style={{
                display: "inline-block",
                padding: "16px 32px",
                borderRadius: "10px",
                background: `linear-gradient(135deg, ${COLORS.ctaStart} 0%, ${COLORS.ctaEnd} 100%)`,
                color: COLORS.ctaText,
                textDecoration: "none",
                fontSize: "17px",
                fontWeight: "600",
                boxShadow: "0 4px 14px rgba(102, 126, 234, 0.35)",
              }}
            >
              Install on Shopify — Free until we drive 30 sales
            </a>
            <p
              style={{
                marginTop: "16px",
                fontSize: "14px",
                color: COLORS.mutedText,
              }}
            >
              No monthly fee · No credit card · Cancel anytime
            </p>
          </div>
        </section>

        {/* Problem */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "680px",
              margin: "0 auto",
              textAlign: "center",
            }}
          >
            <h2
              style={{
                fontSize: "clamp(28px, 5vw, 36px)",
                fontWeight: "700",
                lineHeight: "1.2",
                marginBottom: "24px",
                color: COLORS.bodyText,
              }}
            >
              Shoppers leave without buying.
            </h2>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 18px)",
                lineHeight: "1.6",
                color: COLORS.mutedText,
              }}
            >
              They browse three products and bounce. Your bestsellers never get
              seen. Your repeat customers forget what they came for. You're
              leaving money on every visit.
            </p>
          </div>
        </section>

        {/* Solution */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "800px",
              margin: "0 auto",
              textAlign: "center",
            }}
          >
            <h2
              style={{
                fontSize: "clamp(28px, 5vw, 36px)",
                fontWeight: "700",
                lineHeight: "1.2",
                marginBottom: "24px",
                color: COLORS.bodyText,
              }}
            >
              BetterBundle shows every shopper what to buy next.
            </h2>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 18px)",
                lineHeight: "1.6",
                color: COLORS.mutedText,
              }}
            >
              Personalized recommendations on product pages, thank-you pages,
              post-purchase, checkout, and customer accounts. Built from your
              own order data. Powered by AI.
            </p>
          </div>
        </section>

        {/* Benefits */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "1080px",
              margin: "0 auto",
            }}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: "24px",
              }}
            >
              {BENEFITS.map((benefit) => (
                <div
                  key={benefit.headline}
                  style={{
                    background: COLORS.cardBackground,
                    padding: "24px",
                    borderRadius: "12px",
                  }}
                >
                  <div
                    style={{
                      fontSize: "28px",
                      marginBottom: "12px",
                    }}
                  >
                    {benefit.emoji}
                  </div>
                  <h3
                    style={{
                      fontSize: "clamp(18px, 2.5vw, 20px)",
                      fontWeight: "600",
                      lineHeight: "1.3",
                      marginBottom: "8px",
                      color: COLORS.bodyText,
                    }}
                  >
                    {benefit.headline}
                  </h3>
                  <p
                    style={{
                      fontSize: "clamp(15px, 2vw, 16px)",
                      lineHeight: "1.5",
                      color: COLORS.mutedText,
                    }}
                  >
                    {benefit.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Proof */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "680px",
              margin: "0 auto",
              textAlign: "center",
            }}
          >
            <h2
              style={{
                fontSize: "clamp(28px, 5vw, 36px)",
                fontWeight: "700",
                lineHeight: "1.2",
                marginBottom: "24px",
                color: COLORS.bodyText,
              }}
            >
              We prove the revenue we add. Not guess it.
            </h2>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 18px)",
                lineHeight: "1.6",
                color: COLORS.mutedText,
                marginBottom: "24px",
              }}
            >
              Every recommendation app claims they increase sales. We show you
              exactly how much. A percentage of your shoppers never see our
              recommendations. We compare what they buy to what shoppers who saw
              recommendations buy. The difference is your real lift — measured,
              not estimated.
            </p>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 18px)",
                fontWeight: "600",
                color: COLORS.success,
              }}
            >
              You pay 3% of what we bring in. Not a cent until we've driven 30
              sales.
            </p>
          </div>
        </section>

        {/* Pricing */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "800px",
              margin: "0 auto",
              textAlign: "center",
            }}
          >
            <h2
              style={{
                fontSize: "clamp(28px, 5vw, 36px)",
                fontWeight: "700",
                lineHeight: "1.2",
                marginBottom: "24px",
                color: COLORS.bodyText,
              }}
            >
              Pay only when it works.
            </h2>
            <p
              style={{
                fontSize: "clamp(24px, 4vw, 40px)",
                fontWeight: "700",
                lineHeight: "1.2",
                color: COLORS.success,
                marginBottom: "24px",
              }}
            >
              Free until we've driven 30 sales and $1,000 in attributed revenue.
            </p>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 18px)",
                lineHeight: "1.6",
                color: COLORS.mutedText,
                marginBottom: "32px",
              }}
            >
              After that, 3% of the revenue we attribute to recommendations. You
              set a monthly cap — we never charge above it without your approval.
            </p>
            <a
              href="/auth/login"
              style={{
                display: "inline-block",
                padding: "16px 32px",
                borderRadius: "10px",
                background: `linear-gradient(135deg, ${COLORS.ctaStart} 0%, ${COLORS.ctaEnd} 100%)`,
                color: COLORS.ctaText,
                textDecoration: "none",
                fontSize: "17px",
                fontWeight: "600",
                boxShadow: "0 4px 14px rgba(102, 126, 234, 0.35)",
              }}
            >
              Install — Free to start
            </a>
            <p
              style={{
                marginTop: "16px",
                fontSize: "14px",
                color: COLORS.mutedText,
              }}
            >
              No monthly fee · No card required · Cancel anytime
            </p>
          </div>
        </section>

        {/* FAQ */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "800px",
              margin: "0 auto",
            }}
          >
            <h2
              style={{
                fontSize: "clamp(28px, 5vw, 36px)",
                fontWeight: "700",
                lineHeight: "1.2",
                marginBottom: "32px",
                color: COLORS.bodyText,
                textAlign: "center",
              }}
            >
              Questions
            </h2>
            <div
              style={{
                display: "grid",
                gap: "16px",
              }}
            >
              {FAQ_ITEMS.map((item) => (
                <details
                  key={item.question}
                  style={{
                    border: `1px solid ${COLORS.divider}`,
                    borderRadius: "8px",
                    padding: "16px 24px",
                    background: COLORS.background,
                  }}
                >
                  <summary
                    style={{
                      fontSize: "clamp(16px, 2.5vw, 17px)",
                      fontWeight: "500",
                      lineHeight: "1.4",
                      color: COLORS.bodyText,
                    }}
                  >
                    {item.question}
                  </summary>
                  <p
                    style={{
                      fontSize: "16px",
                      lineHeight: "1.6",
                      color: COLORS.mutedText,
                      marginTop: "12px",
                    }}
                  >
                    {item.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section
          style={{
            padding: "clamp(48px, 6vw, 96px) 24px",
            background: COLORS.background,
          }}
        >
          <div
            style={{
              maxWidth: "800px",
              margin: "0 auto",
              textAlign: "center",
            }}
          >
            <h2
              style={{
                fontSize: "clamp(28px, 5vw, 36px)",
                fontWeight: "700",
                lineHeight: "1.2",
                marginBottom: "16px",
                color: COLORS.bodyText,
              }}
            >
              Ready to turn browsers into buyers?
            </h2>
            <p
              style={{
                fontSize: "clamp(16px, 2.5vw, 18px)",
                lineHeight: "1.6",
                color: COLORS.mutedText,
                marginBottom: "32px",
              }}
            >
              Install BetterBundle. Free until we've driven 30 sales.
            </p>
            <a
              href="/auth/login"
              style={{
                display: "inline-block",
                padding: "16px 32px",
                borderRadius: "10px",
                background: `linear-gradient(135deg, ${COLORS.ctaStart} 0%, ${COLORS.ctaEnd} 100%)`,
                color: COLORS.ctaText,
                textDecoration: "none",
                fontSize: "17px",
                fontWeight: "600",
                boxShadow: "0 4px 14px rgba(102, 126, 234, 0.35)",
              }}
            >
              Install on Shopify
            </a>
          </div>
        </section>

        {/* Footer */}
        <footer
          style={{
            padding: "24px",
            textAlign: "center",
            color: COLORS.mutedText,
            fontSize: "14px",
          }}
        >
          <span style={{ color: COLORS.mutedText }}>
            <a
              href="/privacy-policy"
              style={{ color: COLORS.mutedText, textDecoration: "underline" }}
            >
              Privacy Policy
            </a>
            {" · "}
            <a
              href="/auth/login"
              style={{ color: COLORS.mutedText, textDecoration: "underline" }}
            >
              Log in
            </a>
            {" · "}
            © BetterBundle 2026
          </span>
        </footer>
      </div>
    </>
  );
}
