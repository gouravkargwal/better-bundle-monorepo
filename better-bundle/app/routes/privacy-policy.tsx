import type { MetaFunction } from "@remix-run/node";

export const meta: MetaFunction = () => {
  return [
    { title: "Privacy Policy - BetterBundle" },
    {
      name: "description",
      content:
        "Privacy Policy for BetterBundle AI-Powered Product Recommendations Shopify App",
    },
  ];
};

// This route is publicly accessible - no authentication required
// It can be accessed at: https://betterbundle.site/privacy-policy
export default function PrivacyPolicy() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(to bottom, #f8fafc 0%, #ffffff 100%)",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
      }}
    >
      <style>{`
        * {
          box-sizing: border-box;
        }
        body {
          margin: 0;
          padding: 0;
        }
      `}</style>

      {/* Header */}
      <header
        style={{
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          padding: "2rem 1rem",
          color: "white",
          boxShadow:
            "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        }}
      >
        <div
          style={{
            maxWidth: "1200px",
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div>
            <h1
              style={{
                margin: 0,
                fontSize: "1.75rem",
                fontWeight: "700",
                background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              BetterBundle
            </h1>
            <p
              style={{
                margin: "0.25rem 0 0 0",
                fontSize: "0.875rem",
                opacity: 0.9,
              }}
            >
              AI-powered recommendations that pay for themselves
            </p>
          </div>
          <nav>
            <a
              href="/"
              style={{
                color: "white",
                textDecoration: "none",
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                display: "inline-block",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              Home
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "3rem 1.5rem",
        }}
      >
        <article
          style={{
            background: "white",
            borderRadius: "16px",
            padding: "3rem",
            boxShadow:
              "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
            border: "1px solid #e2e8f0",
          }}
        >
          <h1
            style={{
              fontSize: "2.5rem",
              fontWeight: "700",
              margin: "0 0 1rem 0",
              color: "#1e293b",
              lineHeight: "1.2",
            }}
          >
            Privacy Policy
          </h1>

          <p
            style={{
              color: "#64748b",
              fontSize: "0.875rem",
              marginBottom: "2rem",
              paddingBottom: "1.5rem",
              borderBottom: "1px solid #e2e8f0",
            }}
          >
            <strong style={{ color: "#1e293b" }}>Last Updated:</strong> November
            8, 2025
          </p>

          <div
            style={{
              fontSize: "1rem",
              lineHeight: "1.75",
              color: "#334155",
            }}
          >
            <p style={{ marginBottom: "1.5rem" }}>
              BetterBundle ("we," "our," or "us") is committed to protecting
              your privacy. This Privacy Policy explains how we collect, use,
              disclose, and safeguard your information when you use our Shopify
              app that provides AI-powered product recommendations.
            </p>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                1. Information We Collect
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                To provide our product recommendation services, we collect the
                following types of information:
              </p>

              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: "600",
                  marginTop: "1.5rem",
                  marginBottom: "0.75rem",
                  color: "#334155",
                }}
              >
                Shop Data
              </h3>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Store information (shop domain, store name, settings)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Product data (product information, pricing, inventory,
                  variants)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Order information (order details, order history, revenue data)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Customer data (customer information, purchase history,
                  behavior patterns)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Collection data (product collections, categories)
                </li>
              </ul>

              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: "600",
                  marginTop: "1.5rem",
                  marginBottom: "0.75rem",
                  color: "#334155",
                }}
              >
                Usage Data
              </h3>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  How merchants interact with the app (feature usage, settings
                  preferences)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Performance metrics and analytics data
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Customer interaction data (product views, cart events, search
                  queries)
                </li>
              </ul>

              <h3
                style={{
                  fontSize: "1.125rem",
                  fontWeight: "600",
                  marginTop: "1.5rem",
                  marginBottom: "0.75rem",
                  color: "#334155",
                }}
              >
                Technical Data
              </h3>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  IP addresses and device information for security and analytics
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Browser type and version information
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Session data and authentication tokens
                </li>
              </ul>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                2. How We Use Your Information
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We use the collected information to:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Provide AI-powered product recommendation services to
                  merchants
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Analyze customer behavior and product performance to generate
                  accurate recommendations
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Improve our recommendation algorithms and machine learning
                  models
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Provide analytics, insights, and performance metrics to
                  merchants
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Ensure app security, prevent fraud, and maintain service
                  quality
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Process billing and subscription management
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Provide customer support and respond to inquiries
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Comply with legal obligations and enforce our terms
                </li>
              </ul>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                3. Data Storage and Security
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We implement industry-standard security measures to protect your
                data:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Data is encrypted in transit using TLS/SSL protocols
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Data is stored in secure databases with access controls
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Access to data is restricted to authorized personnel only
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  We regularly review and update our security practices
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Data is stored in compliance with applicable data protection
                  laws
                </li>
              </ul>
              <p style={{ marginBottom: "1rem" }}>
                Your data is stored on secure servers and is only accessible to
                authorized personnel who need it to provide our services.
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                4. Data Sharing and Disclosure
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We do not sell your data. We may share data in the following
                circumstances:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    Service Providers:
                  </strong>{" "}
                  We may share data with third-party service providers necessary
                  to operate the app (hosting, analytics, payment processing).
                  These providers are contractually obligated to protect your
                  data.
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Shopify:</strong> We
                  share data with Shopify as required by the Shopify Partner
                  Program Agreement and API Terms of Use.
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    Legal Requirements:
                  </strong>{" "}
                  We may disclose data when required by law, court order, or to
                  protect our rights and security.
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    Business Transfers:
                  </strong>{" "}
                  In the event of a merger, acquisition, or sale of assets, data
                  may be transferred to the acquiring entity.
                </li>
              </ul>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                5. Your Rights and Choices
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                You have the following rights regarding your personal data:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Access:</strong> Request
                  access to your personal data
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Correction:</strong>{" "}
                  Request correction of inaccurate data
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Deletion:</strong>{" "}
                  Request deletion of your data (subject to legal obligations)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Portability:</strong>{" "}
                  Request a copy of your data in a machine-readable format
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Opt-Out:</strong>{" "}
                  Uninstall the app to stop data collection
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Objection:</strong>{" "}
                  Object to certain types of data processing
                </li>
              </ul>
              <p style={{ marginBottom: "1rem" }}>
                To exercise these rights, contact us at{" "}
                <a
                  href="mailto:gouravkargwal@betterbundle.site"
                  style={{
                    color: "#667eea",
                    textDecoration: "none",
                    fontWeight: "500",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.textDecoration = "underline";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.textDecoration = "none";
                  }}
                >
                  gouravkargwal@betterbundle.site
                </a>
                .
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                6. GDPR Compliance
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We comply with the General Data Protection Regulation (GDPR) and
                other applicable privacy laws. We have implemented the following
                measures:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    Data Request Webhooks:
                  </strong>{" "}
                  We subscribe to Shopify's mandatory compliance webhooks to
                  handle data requests from customers
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>Data Deletion:</strong>{" "}
                  We honor deletion requests through our GDPR webhook handlers
                  (customers/data_request, customers/redact, shop/redact)
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    Shop Data Deletion:
                  </strong>{" "}
                  When you uninstall the app, we delete your shop data within 48
                  hours as required by Shopify
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    HMAC Verification:
                  </strong>{" "}
                  We verify all webhook requests using HMAC signatures to ensure
                  authenticity
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  <strong style={{ color: "#1e293b" }}>
                    Data Minimization:
                  </strong>{" "}
                  We only collect data necessary for providing our services
                </li>
              </ul>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                7. Data Retention
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We retain your data for as long as necessary to provide our
                services and comply with legal obligations:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Active app installations: Data is retained while the app is
                  installed
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  After uninstallation: Shop data is deleted within 48 hours
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Customer data requests: Processed within 30 days as required
                  by GDPR
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Legal requirements: Some data may be retained longer if
                  required by law
                </li>
              </ul>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                8. Cookies and Tracking Technologies
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We use cookies and similar technologies to:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Provide app functionality and authentication
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Analyze app usage and performance
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Improve user experience
                </li>
              </ul>
              <p style={{ marginBottom: "1rem" }}>
                You can manage cookie preferences through your browser settings.
                Note that disabling cookies may affect app functionality.
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                9. Children's Privacy
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                Our app is not intended for users under 18 years of age. We do
                not knowingly collect personal information from children. If you
                believe we have collected information from a child, please
                contact us immediately.
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                10. International Data Transfers
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                Your data may be transferred to and processed in countries other
                than your country of residence. We ensure that appropriate
                safeguards are in place to protect your data in accordance with
                applicable data protection laws.
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                11. Changes to This Privacy Policy
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                We may update this Privacy Policy from time to time. We will
                notify you of significant changes by:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Posting the updated policy on this page
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Updating the "Last Updated" date at the top of this policy
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Sending email notifications for material changes (if you have
                  provided your email)
                </li>
              </ul>
              <p style={{ marginBottom: "1rem" }}>
                Your continued use of the app after changes are posted
                constitutes acceptance of the updated policy.
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                12. Shopify API Terms
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                Our use of Shopify data is governed by the Shopify API License
                and Terms of Use. We comply with all requirements including:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  Using data only for the purposes stated in this policy
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Not sharing merchant data with third parties without consent
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Implementing mandatory compliance webhooks
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Ensuring data security and proper access controls
                </li>
              </ul>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                13. Contact Us
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                If you have questions, concerns, or requests regarding this
                Privacy Policy or our data practices, please contact us:
              </p>
              <div
                style={{
                  background: "#f8fafc",
                  padding: "1.5rem",
                  borderRadius: "8px",
                  marginBottom: "1rem",
                  border: "1px solid #e2e8f0",
                }}
              >
                <p style={{ marginBottom: "0.75rem", marginTop: 0 }}>
                  <strong style={{ color: "#1e293b" }}>Email:</strong>{" "}
                  <a
                    href="mailto:privacy@betterbundle.site"
                    style={{
                      color: "#667eea",
                      textDecoration: "none",
                      fontWeight: "500",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.textDecoration = "underline";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.textDecoration = "none";
                    }}
                  >
                    privacy@betterbundle.site
                  </a>
                </p>
                <p style={{ marginBottom: "0.75rem", marginTop: 0 }}>
                  <strong style={{ color: "#1e293b" }}>Support Email:</strong>{" "}
                  <a
                    href="mailto:support@betterbundle.site"
                    style={{
                      color: "#667eea",
                      textDecoration: "none",
                      fontWeight: "500",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.textDecoration = "underline";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.textDecoration = "none";
                    }}
                  >
                    support@betterbundle.site
                  </a>
                </p>
                <p style={{ marginBottom: 0, marginTop: 0 }}>
                  <strong style={{ color: "#1e293b" }}>Website:</strong>{" "}
                  <a
                    href="https://betterbundle.site"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: "#667eea",
                      textDecoration: "none",
                      fontWeight: "500",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.textDecoration = "underline";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.textDecoration = "none";
                    }}
                  >
                    https://betterbundle.site
                  </a>
                </p>
              </div>
              <p style={{ marginBottom: "1rem" }}>
                We will respond to your inquiry within 30 days as required by
                applicable privacy laws.
              </p>
            </section>

            <section style={{ marginBottom: "2.5rem" }}>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: "600",
                  marginTop: "2.5rem",
                  marginBottom: "1rem",
                  color: "#1e293b",
                  paddingBottom: "0.5rem",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                14. Data Processing Agreement
              </h2>
              <p style={{ marginBottom: "1rem" }}>
                By using BetterBundle, you acknowledge that:
              </p>
              <ul
                style={{
                  marginLeft: "1.5rem",
                  marginBottom: "1.5rem",
                  paddingLeft: "0.5rem",
                }}
              >
                <li style={{ marginBottom: "0.5rem" }}>
                  We act as a data processor when processing data on behalf of
                  merchants
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  Merchants are responsible for obtaining necessary consents
                  from their customers
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  We process data in accordance with merchant instructions and
                  this Privacy Policy
                </li>
                <li style={{ marginBottom: "0.5rem" }}>
                  We implement appropriate technical and organizational measures
                  to protect data
                </li>
              </ul>
            </section>
          </div>
        </article>
      </main>

      {/* Footer */}
      <footer
        style={{
          background: "#1e293b",
          color: "white",
          padding: "2rem 1.5rem",
          marginTop: "3rem",
        }}
      >
        <div
          style={{
            maxWidth: "1200px",
            margin: "0 auto",
            textAlign: "center",
          }}
        >
          <p style={{ margin: 0, opacity: 0.8, fontSize: "0.875rem" }}>
            © {new Date().getFullYear()} BetterBundle. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
