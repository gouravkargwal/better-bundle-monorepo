import { Banner, BlockStack, ProgressBar, Text } from "@shopify/polaris";

export function BillingStatus({
  billingData,
  formatCurrency,
  getStatusBadge,
  formatDate,
}: any) {
  if (!billingData?.billing_plan) {
    return (
      <Banner tone="warning">
        <Text as="p">No billing plan found. Please contact support.</Text>
      </Banner>
    );
  }

  const plan = billingData.billing_plan;
  const trialStatus = plan.trial_status;

  // Ensure trial status values are numbers
  const safeTrialStatus = {
    is_trial_active: trialStatus?.is_trial_active || false,
    trial_threshold: Number(trialStatus?.trial_threshold) || 0,
    trial_revenue: Number(trialStatus?.trial_revenue) || 0,
    remaining_revenue: Math.max(
      0,
      (Number(trialStatus?.trial_threshold) || 0) -
        (Number(trialStatus?.trial_revenue) || 0),
    ),
    trial_progress:
      trialStatus?.trial_threshold > 0
        ? ((Number(trialStatus?.trial_revenue) || 0) /
            (Number(trialStatus?.trial_threshold) || 1)) *
          100
        : 0,
  };

  return (
    <BlockStack gap="500">
      {/* Billing Plan Overview */}
      <div
        style={{
          padding: "40px 32px",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          borderRadius: "24px",
          color: "white",
          textAlign: "center",
          position: "relative",
          overflow: "hidden",
          boxShadow:
            "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        }}
      >
        <div style={{ position: "relative", zIndex: 2 }}>
          {/* Hero Badge */}
          <div style={{ marginBottom: "16px" }}>
            <div
              style={{
                display: "inline-block",
                padding: "8px 16px",
                backgroundColor: "rgba(255, 255, 255, 0.2)",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                color: "white",
                fontWeight: "600",
                borderRadius: "8px",
                fontSize: "14px",
              }}
            >
              💳 Billing Dashboard
            </div>
          </div>

          {/* Main Headline */}
          <div
            style={{
              fontSize: "3rem",
              lineHeight: "1.1",
              marginBottom: "16px",
              background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              fontWeight: "bold",
            }}
          >
            {plan.name}
          </div>

          {/* Subheadline */}
          <div
            style={{
              marginBottom: "20px",
              maxWidth: "600px",
              margin: "0 auto 20px",
            }}
          >
            <div
              style={{
                color: "rgba(255,255,255,0.95)",
                lineHeight: "1.6",
                fontWeight: "500",
                fontSize: "1.25rem",
              }}
            >
              {plan.type.replace("_", " ").toUpperCase()} Plan •{" "}
              {getStatusBadge(plan.status)}
            </div>
          </div>

          {/* Key Benefits Row */}
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: "24px",
              marginBottom: "24px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "#10B981",
                  borderRadius: "50%",
                }}
              />
              <span
                style={{
                  color: "rgba(255,255,255,0.9)",
                  fontSize: "1.125rem",
                }}
              >
                Effective: {formatDate(plan.effective_from)}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "#10B981",
                  borderRadius: "50%",
                }}
              />
              <span
                style={{
                  color: "rgba(255,255,255,0.9)",
                  fontSize: "1.125rem",
                }}
              >
                Currency: {plan.currency || "USD"}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "#10B981",
                  borderRadius: "50%",
                }}
              />
              <span
                style={{
                  color: "rgba(255,255,255,0.9)",
                  fontSize: "1.125rem",
                }}
              >
                Rate: 3%
              </span>
            </div>
          </div>

          {/* Enhanced Decorative elements */}
          <div
            style={{
              position: "absolute",
              top: "-100px",
              right: "-100px",
              width: "300px",
              height: "300px",
              background:
                "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-80px",
              left: "-80px",
              width: "250px",
              height: "250px",
              background:
                "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "-50px",
              width: "100px",
              height: "100px",
              background: "rgba(255,255,255,0.03)",
              borderRadius: "50%",
              zIndex: 1,
            }}
          />
        </div>
      </div>

      {/* Trial Status */}
      {safeTrialStatus.is_trial_active ? (
        <div
          style={{
            padding: "40px 32px",
            background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
            borderRadius: "24px",
            color: "white",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
            boxShadow:
              "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
          }}
        >
          <div style={{ position: "relative", zIndex: 2 }}>
            <div style={{ marginBottom: "16px" }}>
              <div
                style={{
                  display: "inline-block",
                  padding: "8px 16px",
                  backgroundColor: "rgba(255, 255, 255, 0.2)",
                  border: "1px solid rgba(255, 255, 255, 0.3)",
                  color: "white",
                  fontWeight: "600",
                  borderRadius: "8px",
                  fontSize: "14px",
                }}
              >
                🎉 Free Trial Active
              </div>
            </div>

            <div
              style={{
                fontSize: "2.5rem",
                lineHeight: "1.1",
                marginBottom: "16px",
                background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                fontWeight: "bold",
              }}
            >
              Trial Progress
            </div>

            <div
              style={{
                marginBottom: "20px",
                maxWidth: "600px",
                margin: "0 auto 20px",
              }}
            >
              <div
                style={{
                  color: "rgba(255,255,255,0.95)",
                  lineHeight: "1.6",
                  fontWeight: "500",
                  fontSize: "1.25rem",
                }}
              >
                Generate{" "}
                {formatCurrency(
                  safeTrialStatus.remaining_revenue,
                  plan.currency,
                )}{" "}
                more in attributed revenue to start billing
              </div>
            </div>

            <div
              style={{
                marginBottom: "24px",
                padding: "20px",
                backgroundColor: "rgba(255,255,255,0.12)",
                borderRadius: "16px",
                border: "1px solid rgba(255,255,255,0.2)",
                backdropFilter: "blur(10px)",
                maxWidth: "500px",
                margin: "0 auto 24px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "12px",
                  marginBottom: "16px",
                }}
              >
                <div
                  style={{
                    width: "32px",
                    height: "32px",
                    backgroundColor: "rgba(255, 255, 255, 0.2)",
                    borderRadius: "8px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <span
                    style={{
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    📊
                  </span>
                </div>
                <div
                  style={{
                    fontSize: "1.25rem",
                    fontWeight: "bold",
                    color: "white",
                  }}
                >
                  Progress: {Math.round(safeTrialStatus.trial_progress)}%
                  Complete
                </div>
              </div>

              <ProgressBar
                progress={safeTrialStatus.trial_progress}
                size="large"
              />

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                  gap: "16px",
                  marginTop: "20px",
                }}
              >
                <div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.8)",
                      fontSize: "0.875rem",
                    }}
                  >
                    Current Revenue
                  </div>
                  <div
                    style={{
                      color: "white",
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    {formatCurrency(
                      safeTrialStatus.trial_revenue,
                      plan.currency,
                    )}
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.8)",
                      fontSize: "0.875rem",
                    }}
                  >
                    Trial Threshold
                  </div>
                  <div
                    style={{
                      color: "white",
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    {formatCurrency(
                      safeTrialStatus.trial_threshold,
                      plan.currency,
                    )}
                  </div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.7)",
                      fontSize: "0.75rem",
                    }}
                  >
                    (Equivalent to $200 USD)
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.8)",
                      fontSize: "0.875rem",
                    }}
                  >
                    Remaining
                  </div>
                  <div
                    style={{
                      color: "white",
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    {formatCurrency(
                      safeTrialStatus.remaining_revenue,
                      plan.currency,
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Enhanced Decorative elements */}
            <div
              style={{
                position: "absolute",
                top: "-100px",
                right: "-100px",
                width: "300px",
                height: "300px",
                background:
                  "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
                borderRadius: "50%",
                zIndex: 1,
              }}
            />
            <div
              style={{
                position: "absolute",
                bottom: "-80px",
                left: "-80px",
                width: "250px",
                height: "250px",
                background:
                  "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
                borderRadius: "50%",
                zIndex: 1,
              }}
            />
          </div>
        </div>
      ) : (
        <div
          style={{
            padding: "40px 32px",
            background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
            borderRadius: "24px",
            color: "white",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
            boxShadow:
              "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
          }}
        >
          <div style={{ position: "relative", zIndex: 2 }}>
            <div style={{ marginBottom: "16px" }}>
              <div
                style={{
                  display: "inline-block",
                  padding: "8px 16px",
                  backgroundColor: "rgba(255, 255, 255, 0.2)",
                  border: "1px solid rgba(255, 255, 255, 0.3)",
                  color: "white",
                  fontWeight: "600",
                  borderRadius: "8px",
                  fontSize: "14px",
                }}
              >
                💰 Trial Completed - Billing Active
              </div>
            </div>

            <div
              style={{
                fontSize: "2.5rem",
                lineHeight: "1.1",
                marginBottom: "16px",
                background: "linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                fontWeight: "bold",
              }}
            >
              Billing Active
            </div>

            <div
              style={{
                marginBottom: "20px",
                maxWidth: "600px",
                margin: "0 auto 20px",
              }}
            >
              <div
                style={{
                  color: "rgba(255,255,255,0.95)",
                  lineHeight: "1.6",
                  fontWeight: "500",
                  fontSize: "1.25rem",
                }}
              >
                Your trial has ended. You're now being charged 3% of attributed
                revenue.
              </div>
            </div>

            <div
              style={{
                marginBottom: "24px",
                padding: "20px",
                backgroundColor: "rgba(255,255,255,0.12)",
                borderRadius: "16px",
                border: "1px solid rgba(255,255,255,0.2)",
                backdropFilter: "blur(10px)",
                maxWidth: "500px",
                margin: "0 auto 24px",
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                  gap: "16px",
                }}
              >
                <div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.8)",
                      fontSize: "0.875rem",
                    }}
                  >
                    Trial Revenue
                  </div>
                  <div
                    style={{
                      color: "white",
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    {formatCurrency(
                      safeTrialStatus.trial_revenue,
                      plan.currency,
                    )}
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.8)",
                      fontSize: "0.875rem",
                    }}
                  >
                    Billing Rate
                  </div>
                  <div
                    style={{
                      color: "white",
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    3%
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      color: "rgba(255,255,255,0.8)",
                      fontSize: "0.875rem",
                    }}
                  >
                    Status
                  </div>
                  <div
                    style={{
                      color: "white",
                      fontSize: "1.125rem",
                      fontWeight: "bold",
                    }}
                  >
                    Active
                  </div>
                </div>
              </div>
            </div>

            {/* Enhanced Decorative elements */}
            <div
              style={{
                position: "absolute",
                top: "-100px",
                right: "-100px",
                width: "300px",
                height: "300px",
                background:
                  "radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%)",
                borderRadius: "50%",
                zIndex: 1,
              }}
            />
            <div
              style={{
                position: "absolute",
                bottom: "-80px",
                left: "-80px",
                width: "250px",
                height: "250px",
                background:
                  "radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%)",
                borderRadius: "50%",
                zIndex: 1,
              }}
            />
          </div>
        </div>
      )}
    </BlockStack>
  );
}
