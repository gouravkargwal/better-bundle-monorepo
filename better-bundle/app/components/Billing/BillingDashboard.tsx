import React, { useState, useEffect } from "react";
import {
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Badge,
  Spinner,
  Banner,
  Box,
  Layout,
} from "@shopify/polaris";

interface BillingData {
  billing_plan: {
    id: string;
    name: string;
    type: string;
    status: string;
    configuration: any;
    effective_from: string;
    currency?: string;
    trial_status: {
      is_trial_active: boolean;
      trial_threshold: number;
      trial_revenue: number;
      remaining_revenue: number;
      trial_progress: number;
    };
  } | null;
  recent_invoices: Array<{
    id: string;
    invoice_number: string;
    status: string;
    total: number;
    currency: string;
    period_start: string;
    period_end: string;
    due_date: string;
    created_at: string;
  }>;
  recent_events: Array<{
    id: string;
    type: string;
    data: any;
    occurred_at: string;
  }>;
}

export function BillingDashboard() {
  const [billingData, setBillingData] = useState<BillingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    try {
      setLoading(true);
      setError(null);

      console.log("Loading billing data...");

      // Load billing status
      const billingResponse = await fetch("/api/billing");
      const billingResult = await billingResponse.json();

      console.log("Billing API response:", billingResult);

      if (!billingResult.success) {
        throw new Error(billingResult.error || "Failed to load billing data");
      }

      setBillingData(billingResult.data);
      console.log("Billing data set:", billingResult.data);
    } catch (err) {
      console.error("Error loading billing data:", err);
      setError(
        err instanceof Error ? err.message : "Failed to load billing data",
      );
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "paid":
        return <Badge tone="success">Paid</Badge>;
      case "pending":
        return <Badge tone="warning">Pending</Badge>;
      case "overdue":
        return <Badge tone="critical">Overdue</Badge>;
      case "active":
        return <Badge tone="success">Active</Badge>;
      case "inactive":
        return <Badge tone="info">Inactive</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const getCurrencySymbol = (currencyCode: string) => {
    const symbols: { [key: string]: string } = {
      USD: "$",
      EUR: "€",
      GBP: "£",
      CAD: "C$",
      AUD: "A$",
      JPY: "¥",
      CHF: "CHF",
      SEK: "kr",
      NOK: "kr",
      DKK: "kr",
      PLN: "zł",
      CZK: "Kč",
      HUF: "Ft",
      BGN: "лв",
      RON: "lei",
      HRK: "kn",
      RSD: "дин",
      MKD: "ден",
      BAM: "КМ",
      ALL: "L",
      ISK: "kr",
      UAH: "₴",
      RUB: "₽",
      BYN: "Br",
      KZT: "₸",
      GEL: "₾",
      AMD: "֏",
      AZN: "₼",
      KGS: "с",
      TJS: "SM",
      TMT: "T",
      UZS: "so'm",
      MNT: "₮",
      KHR: "៛",
      LAK: "₭",
      VND: "₫",
      THB: "฿",
      MYR: "RM",
      SGD: "S$",
      IDR: "Rp",
      PHP: "₱",
      INR: "₹",
      PKR: "₨",
      BDT: "৳",
      LKR: "₨",
      NPR: "₨",
      BTN: "Nu",
      MVR: "ރ",
      AFN: "؋",
      IRR: "﷼",
      IQD: "ع.د",
      JOD: "د.ا",
      KWD: "د.ك",
      LBP: "ل.ل",
      OMR: "ر.ع",
      QAR: "ر.ق",
      SAR: "ر.س",
      SYP: "ل.س",
      AED: "د.إ",
      YER: "﷼",
      ILS: "₪",
      JMD: "J$",
      BBD: "Bds$",
      BZD: "BZ$",
      XCD: "EC$",
      KYD: "CI$",
      TTD: "TT$",
      AWG: "ƒ",
      BSD: "B$",
      BMD: "BD$",
      BND: "B$",
      FJD: "FJ$",
      GYD: "G$",
      LRD: "L$",
      SBD: "SI$",
      SRD: "Sr$",
      TVD: "TV$",
      VES: "Bs.S",
      ARS: "$",
      BOB: "Bs",
      BRL: "R$",
      CLP: "$",
      COP: "$",
      CRC: "₡",
      CUP: "$",
      DOP: "RD$",
      GTQ: "Q",
      HNL: "L",
      MXN: "$",
      NIO: "C$",
      PAB: "B/.",
      PEN: "S/",
      PYG: "₲",
      UYU: "$U",
      VEF: "Bs",
      ZAR: "R",
      BWP: "P",
      LSL: "L",
      NAD: "N$",
      SZL: "L",
      ZMW: "ZK",
      ZWL: "Z$",
      AOA: "Kz",
      CDF: "FC",
      GMD: "D",
      GNF: "FG",
      KES: "KSh",
      MAD: "د.م.",
      MGA: "Ar",
      MUR: "₨",
      NGN: "₦",
      RWF: "RF",
      SLL: "Le",
      SOS: "S",
      TZS: "TSh",
      UGX: "USh",
      XAF: "FCFA",
      XOF: "CFA",
    };
    return symbols[currencyCode] || currencyCode;
  };

  const formatCurrency = (amount: number, currencyCode: string = "USD") => {
    const symbol = getCurrencySymbol(currencyCode);
    return `${symbol}${amount.toFixed(2)}`;
  };

  if (loading) {
    return (
      <Box padding="400">
        <InlineStack align="center">
          <Spinner size="large" />
          <Text as="p">Loading billing information...</Text>
        </InlineStack>
      </Box>
    );
  }

  if (error) {
    return (
      <Box padding="400">
        <Banner tone="critical">
          <Text as="p">{error}</Text>
          <Button onClick={loadBillingData}>Try Again</Button>
        </Banner>
      </Box>
    );
  }

  if (!billingData) {
    return (
      <Box padding="400">
        <Banner>
          <Text as="p">
            No billing information available. Please refresh the page or contact
            support if this persists.
          </Text>
        </Banner>
      </Box>
    );
  }

  return (
    <Layout>
      {/* Billing Information Only */}
      <Layout.Section>
        <BlockStack gap="500">
          {/* Billing Plan Status */}
          <BlockStack gap="400">
            <div
              style={{
                padding: "24px",
                backgroundColor: "#FEF3C7",
                borderRadius: "12px",
                border: "1px solid #FCD34D",
              }}
            >
              <div style={{ color: "#92400E" }}>
                <Text as="h2" variant="headingLg" fontWeight="bold">
                  💳 Billing Plan
                </Text>
              </div>
              <div style={{ marginTop: "8px" }}>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Your current billing plan and status
                </Text>
              </div>
            </div>

            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between">
                  <Text as="h3" variant="headingMd">
                    Plan Details
                  </Text>
                  {billingData.billing_plan &&
                    getStatusBadge(billingData.billing_plan.status)}
                </InlineStack>

                {billingData.billing_plan ? (
                  <BlockStack gap="200">
                    <Text as="p" variant="bodyMd">
                      <strong>Plan:</strong> {billingData.billing_plan.name}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      <strong>Type:</strong>{" "}
                      {billingData.billing_plan.type
                        .replace("_", " ")
                        .toUpperCase()}
                    </Text>
                    <Text as="p" variant="bodyMd">
                      <strong>Effective:</strong>{" "}
                      {formatDate(billingData.billing_plan.effective_from)}
                    </Text>
                    {billingData.billing_plan.currency && (
                      <Text as="p" variant="bodyMd">
                        <strong>Currency:</strong>{" "}
                        {billingData.billing_plan.currency} (
                        {getCurrencySymbol(billingData.billing_plan.currency)})
                      </Text>
                    )}
                    {billingData.billing_plan.configuration
                      ?.subscription_id && (
                      <Text as="p" variant="bodyMd">
                        <strong>Subscription:</strong>{" "}
                        {billingData.billing_plan.configuration
                          .subscription_status || "Pending"}
                      </Text>
                    )}

                    {/* Trial Status */}
                    {billingData.billing_plan.trial_status.is_trial_active ? (
                      <div
                        style={{
                          padding: "16px",
                          backgroundColor: "#F0F9FF",
                          borderRadius: "8px",
                          border: "1px solid #BAE6FD",
                          marginTop: "12px",
                        }}
                      >
                        <BlockStack gap="200">
                          <InlineStack align="space-between">
                            <Text as="h4" variant="headingSm" fontWeight="bold">
                              🎉 Free Trial Active
                            </Text>
                            <Badge tone="info">
                              {`${Math.round(
                                billingData.billing_plan.trial_status
                                  .trial_progress,
                              )}% Complete`}
                            </Badge>
                          </InlineStack>

                          <Text as="p" variant="bodyMd" tone="subdued">
                            Generate{" "}
                            {formatCurrency(
                              billingData.billing_plan.trial_status
                                .remaining_revenue,
                              billingData.billing_plan.currency || "USD",
                            )}{" "}
                            more in attributed revenue to start billing
                          </Text>

                          <div style={{ marginTop: "8px" }}>
                            <div
                              style={{
                                width: "100%",
                                height: "8px",
                                backgroundColor: "#E5E7EB",
                                borderRadius: "4px",
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  width: `${billingData.billing_plan.trial_status.trial_progress}%`,
                                  height: "100%",
                                  backgroundColor: "#3B82F6",
                                  transition: "width 0.3s ease",
                                }}
                              />
                            </div>
                          </div>

                          <Text as="p" variant="bodySm" tone="subdued">
                            Current attributed revenue:{" "}
                            {formatCurrency(
                              billingData.billing_plan.trial_status
                                .trial_revenue,
                              billingData.billing_plan.currency || "USD",
                            )}{" "}
                            /{" "}
                            {formatCurrency(
                              billingData.billing_plan.trial_status
                                .trial_threshold,
                              billingData.billing_plan.currency || "USD",
                            )}
                          </Text>
                        </BlockStack>
                      </div>
                    ) : (
                      <div
                        style={{
                          padding: "16px",
                          backgroundColor: "#F0FDF4",
                          borderRadius: "8px",
                          border: "1px solid #BBF7D0",
                          marginTop: "12px",
                        }}
                      >
                        <BlockStack gap="200">
                          <InlineStack align="space-between">
                            <Text as="h4" variant="headingSm" fontWeight="bold">
                              💰 Trial Completed - Billing Active
                            </Text>
                            <Badge tone="success">Paid Plan</Badge>
                          </InlineStack>

                          <Text as="p" variant="bodyMd" tone="subdued">
                            Your trial has ended. You're now being charged 3% of
                            attributed revenue.
                          </Text>

                          <Text as="p" variant="bodySm" tone="subdued">
                            Trial completed with{" "}
                            {formatCurrency(
                              billingData.billing_plan.trial_status
                                .trial_revenue,
                              billingData.billing_plan.currency || "USD",
                            )}{" "}
                            in attributed revenue
                          </Text>
                        </BlockStack>
                      </div>
                    )}

                    {/* Billing Information - Show when trial is completed */}
                    {billingData.billing_plan &&
                      !billingData.billing_plan.trial_status
                        .is_trial_active && (
                        <div
                          style={{
                            padding: "16px",
                            backgroundColor: "#F8FAFC",
                            borderRadius: "8px",
                            border: "1px solid #E2E8F0",
                            marginTop: "12px",
                          }}
                        >
                          <BlockStack gap="200">
                            <Text as="h4" variant="headingSm" fontWeight="bold">
                              💳 Billing Information
                            </Text>

                            <Text as="p" variant="bodyMd" tone="subdued">
                              You're now being charged 3% of attributed revenue
                              from your recommendations.
                            </Text>

                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fit, minmax(150px, 1fr))",
                                gap: "12px",
                                marginTop: "8px",
                              }}
                            >
                              <div
                                style={{
                                  padding: "12px",
                                  backgroundColor: "#FFFFFF",
                                  borderRadius: "6px",
                                  border: "1px solid #E5E7EB",
                                }}
                              >
                                <Text as="p" variant="bodySm" tone="subdued">
                                  Billing Rate
                                </Text>
                                <Text
                                  as="p"
                                  variant="headingMd"
                                  fontWeight="bold"
                                >
                                  3%
                                </Text>
                              </div>

                              <div
                                style={{
                                  padding: "12px",
                                  backgroundColor: "#FFFFFF",
                                  borderRadius: "6px",
                                  border: "1px solid #E5E7EB",
                                }}
                              >
                                <Text as="p" variant="bodySm" tone="subdued">
                                  Trial Revenue
                                </Text>
                                <Text
                                  as="p"
                                  variant="headingMd"
                                  fontWeight="bold"
                                >
                                  {formatCurrency(
                                    billingData.billing_plan.trial_status
                                      .trial_revenue,
                                    billingData.billing_plan.currency || "USD",
                                  )}
                                </Text>
                              </div>
                            </div>
                          </BlockStack>
                        </div>
                      )}
                  </BlockStack>
                ) : (
                  <Banner tone="warning">
                    <Text as="p">
                      No active billing plan found. Please contact support.
                    </Text>
                  </Banner>
                )}
              </BlockStack>
            </Card>
          </BlockStack>
        </BlockStack>
      </Layout.Section>
    </Layout>
  );
}
