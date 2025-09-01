/**
 * Billing Dashboard Component
 * Shows performance tiers, commission calculations, and billing history
 */

import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts";

interface PerformanceTier {
  name: string;
  minConversionRate: number;
  maxConversionRate: number;
  baseCommissionRate: number;
  performanceBonus: number;
  totalCommissionRate: number;
  color: string;
}

interface BillingCalculation {
  tier: PerformanceTier;
  commissionAmount: number;
  performanceScore: number;
  tierUpgradePotential: number;
  nextTierBonus: number;
  billingPeriod: string;
  startDate: Date;
  endDate: Date;
}

interface PerformanceMetrics {
  conversionRate: number;
  revenuePerRecommendation: number;
  totalRecommendationsDisplayed: number;
  totalRecommendationsClicked: number;
  totalRecommendationsAddedToCart: number;
  totalRecommendationsPurchased: number;
  totalRevenueAttributed: number;
  averageOrderValue: number;
  customerRetentionRate: number;
  bundleEffectiveness: number;
}

const PERFORMANCE_TIERS: PerformanceTier[] = [
  {
    name: "Bronze",
    minConversionRate: 0,
    maxConversionRate: 5,
    baseCommissionRate: 0.015,
    performanceBonus: 0.0,
    totalCommissionRate: 0.015,
    color: "#CD7F32",
  },
  {
    name: "Silver",
    minConversionRate: 5,
    maxConversionRate: 10,
    baseCommissionRate: 0.015,
    performanceBonus: 0.005,
    totalCommissionRate: 0.02,
    color: "#C0C0C0",
  },
  {
    name: "Gold",
    minConversionRate: 10,
    maxConversionRate: 15,
    baseCommissionRate: 0.015,
    performanceBonus: 0.01,
    totalCommissionRate: 0.025,
    color: "#FFD700",
  },
  {
    name: "Platinum",
    minConversionRate: 15,
    maxConversionRate: 100,
    baseCommissionRate: 0.015,
    performanceBonus: 0.015,
    totalCommissionRate: 0.03,
    color: "#E5E4E2",
  },
];

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8"];

export default function BillingDashboard() {
  const [billingData, setBillingData] = useState<{
    currentPeriod: BillingCalculation;
    historicalBilling: BillingCalculation[];
    performanceTrends: any[];
    recommendations: string[];
  } | null>(null);
  const [billingStatus, setBillingStatus] = useState<{
    subscription?: {
      id: string;
      planName: string;
      status: string;
      trialDays: number;
      currentPeriodEnd: string;
      nextBillingDate: string;
    };
    charges: Array<{
      id: string;
      amount: number;
      currency: string;
      description: string;
      billingPeriod: string;
      status: string;
      createdAt: string;
      dueDate: string;
      paidAt?: string;
    }>;
    totalPaid: number;
    totalPending: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState(6);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);

  useEffect(() => {
    fetchBillingData();
    fetchBillingStatus();
  }, [timeRange]);

  const fetchBillingStatus = async () => {
    try {
      const response = await fetch("/api/billing/manage");
      if (response.ok) {
        const data = await response.json();
        setBillingStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch billing status:", err);
    }
  };

  const createSubscription = async () => {
    try {
      setSubscriptionLoading(true);
      const formData = new FormData();
      formData.append("action", "create_subscription");

      const response = await fetch("/api/billing/manage", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        await fetchBillingStatus();
      } else {
        const error = await response.json();
        setError(error.error || "Failed to create subscription");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubscriptionLoading(false);
    }
  };

  const cancelSubscription = async () => {
    try {
      setSubscriptionLoading(true);
      const formData = new FormData();
      formData.append("action", "cancel_subscription");

      const response = await fetch("/api/billing/manage", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        await fetchBillingStatus();
      } else {
        const error = await response.json();
        setError(error.error || "Failed to cancel subscription");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubscriptionLoading(false);
    }
  };

  const fetchBillingData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/billing?months=${timeRange}`);

      if (!response.ok) {
        throw new Error("Failed to fetch billing data");
      }

      const data = await response.json();
      setBillingData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat("en-US").format(num);
  };

  const formatPercentage = (num: number) => {
    return `${num.toFixed(2)}%`;
  };

  const getCurrentTier = () => {
    return billingData?.currentPeriod?.tier || PERFORMANCE_TIERS[0];
  };

  const getNextTier = () => {
    const currentTier = getCurrentTier();
    return PERFORMANCE_TIERS.find(
      (tier) => tier.minConversionRate > currentTier.minConversionRate,
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center p-8">
        <div className="text-red-600 mb-4">
          Error loading billing data: {error}
        </div>
        <Button onClick={fetchBillingData}>Retry</Button>
      </div>
    );
  }

  if (!billingData) {
    return <div>No billing data available</div>;
  }

  const {
    currentPeriod,
    historicalBilling,
    performanceTrends,
    recommendations,
  } = billingData;
  const currentTier = currentPeriod.tier;
  const nextTier = getNextTier();

  // Prepare chart data
  const tierComparisonData = PERFORMANCE_TIERS.map((tier) => ({
    name: tier.name,
    baseRate: tier.baseCommissionRate * 100,
    bonus: tier.performanceBonus * 100,
    total: tier.totalCommissionRate * 100,
    color: tier.color,
  }));

  const performanceTrendData = performanceTrends.map((trend) => ({
    period: trend.period,
    performanceScore: trend.performanceScore,
    commissionRate: trend.commissionRate * 100,
    commissionAmount: trend.commissionAmount,
    trend: trend.trend,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Performance Billing Dashboard</h1>
          <p className="text-gray-600">
            Track your performance tier and commission earnings
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={timeRange === 3 ? "default" : "outline"}
            onClick={() => setTimeRange(3)}
          >
            3 Months
          </Button>
          <Button
            variant={timeRange === 6 ? "default" : "outline"}
            onClick={() => setTimeRange(6)}
          >
            6 Months
          </Button>
          <Button
            variant={timeRange === 12 ? "default" : "outline"}
            onClick={() => setTimeRange(12)}
          >
            12 Months
          </Button>
        </div>
      </div>

      {/* Current Performance Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Current Tier</CardTitle>
            <Badge
              variant="secondary"
              style={{ backgroundColor: currentTier.color, color: "white" }}
            >
              {currentTier.name}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatPercentage(currentTier.totalCommissionRate * 100)}
            </div>
            <p className="text-xs text-muted-foreground">
              Total Commission Rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Performance Score
            </CardTitle>
            <Badge variant="secondary">Score</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {currentPeriod.performanceScore}/100
            </div>
            <p className="text-xs text-muted-foreground">
              Based on conversion rate & revenue
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Commission Due
            </CardTitle>
            <Badge variant="secondary">Current</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(currentPeriod.commissionAmount)}
            </div>
            <p className="text-xs text-muted-foreground">This billing period</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Next Tier Bonus
            </CardTitle>
            <Badge variant="secondary">Potential</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(currentPeriod.nextTierBonus)}
            </div>
            <p className="text-xs text-muted-foreground">
              {nextTier ? `Reach ${nextTier.name} tier` : "Already at top tier"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Performance Tiers Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Tiers & Commission Rates</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {PERFORMANCE_TIERS.map((tier, index) => (
              <div
                key={tier.name}
                className={`p-4 rounded-lg border-2 ${
                  tier.name === currentTier.name
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: tier.color }}
                    ></div>
                    <div>
                      <h3 className="font-semibold">{tier.name} Tier</h3>
                      <p className="text-sm text-gray-600">
                        {tier.minConversionRate}% -{" "}
                        {tier.maxConversionRate === 100
                          ? "∞"
                          : tier.maxConversionRate}
                        % conversion rate
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold">
                      {formatPercentage(tier.totalCommissionRate * 100)}
                    </div>
                    <div className="text-sm text-gray-600">
                      {tier.baseCommissionRate * 100}% base +{" "}
                      {tier.performanceBonus * 100}% bonus
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Charts */}
      <Tabs defaultValue="tiers" className="space-y-4">
        <TabsList>
          <TabsTrigger value="tiers">Tier Comparison</TabsTrigger>
          <TabsTrigger value="trends">Performance Trends</TabsTrigger>
          <TabsTrigger value="recommendations">Optimization Tips</TabsTrigger>
        </TabsList>

        <TabsContent value="tiers" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Commission Rate Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={tierComparisonData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="total" fill="#8884d8" name="Total Rate" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance Score Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={[
                        {
                          name: "Excellent",
                          value: currentPeriod.performanceScore >= 80 ? 1 : 0,
                        },
                        {
                          name: "Good",
                          value: currentPeriod.performanceScore >= 60 ? 1 : 0,
                        },
                        {
                          name: "Average",
                          value: currentPeriod.performanceScore >= 40 ? 1 : 0,
                        },
                        {
                          name: "Needs Improvement",
                          value: currentPeriod.performanceScore < 40 ? 1 : 0,
                        },
                      ]}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) =>
                        `${name} ${(percent * 100).toFixed(0)}%`
                      }
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {COLORS.map((color, index) => (
                        <Cell key={`cell-${index}`} fill={color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Trends Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={performanceTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" />
                  <YAxis />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="performanceScore"
                    stroke="#8884d8"
                    name="Performance Score"
                  />
                  <Line
                    type="monotone"
                    dataKey="commissionRate"
                    stroke="#82ca9d"
                    name="Commission Rate %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="recommendations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Optimization Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    className="p-3 bg-blue-50 rounded-lg border-l-4 border-blue-500"
                  >
                    <p className="text-sm">{recommendation}</p>
                  </div>
                ))}

                {recommendations.length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    <p>Great job! Your performance is optimal.</p>
                    <p className="text-sm">Keep up the excellent work!</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Tier Upgrade Path */}
      {nextTier && (
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader>
            <CardTitle className="text-blue-800">
              🚀 Tier Upgrade Path
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-blue-800">
                    Next Tier: {nextTier.name}
                  </h3>
                  <p className="text-blue-600">
                    Increase conversion rate by{" "}
                    {formatPercentage(currentPeriod.tierUpgradePotential)}
                    to reach {nextTier.name} tier
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-blue-800">
                    {formatCurrency(currentPeriod.nextTierBonus)}
                  </div>
                  <div className="text-sm text-blue-600">
                    Additional monthly earnings
                  </div>
                </div>
              </div>

              <div className="w-full bg-blue-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, (currentTier.maxConversionRate / nextTier.minConversionRate) * 100)}%`,
                  }}
                ></div>
              </div>

              <p className="text-sm text-blue-700">
                <strong>Tip:</strong> Focus on improving recommendation
                relevance, user experience, and product placement to boost your
                conversion rate.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Subscription Management */}
      <Card>
        <CardHeader>
          <CardTitle>Billing Subscription</CardTitle>
        </CardHeader>
        <CardContent>
          {billingStatus?.subscription ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg border border-green-200">
                <div>
                  <h3 className="font-semibold text-green-800">
                    Active Subscription
                  </h3>
                  <p className="text-green-600">
                    Plan: {billingStatus.subscription.planName}
                  </p>
                  <p className="text-sm text-green-600">
                    Next billing:{" "}
                    {new Date(
                      billingStatus.subscription.nextBillingDate,
                    ).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right">
                  <Badge
                    variant="secondary"
                    className="bg-green-100 text-green-800"
                  >
                    {billingStatus.subscription.status}
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-3 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">
                    {formatCurrency(billingStatus.totalPaid)}
                  </div>
                  <div className="text-sm text-blue-600">Total Paid</div>
                </div>
                <div className="text-center p-3 bg-orange-50 rounded-lg">
                  <div className="text-2xl font-bold text-orange-600">
                    {formatCurrency(billingStatus.totalPending)}
                  </div>
                  <div className="text-sm text-orange-600">Pending Charges</div>
                </div>
              </div>

              <Button
                variant="outline"
                onClick={cancelSubscription}
                disabled={subscriptionLoading}
                className="w-full"
              >
                {subscriptionLoading ? "Cancelling..." : "Cancel Subscription"}
              </Button>
            </div>
          ) : (
            <div className="text-center p-8">
              <div className="text-gray-500 mb-4">
                <p>No active billing subscription found.</p>
                <p className="text-sm">
                  Set up billing to start tracking commissions.
                </p>
              </div>
              <Button
                onClick={createSubscription}
                disabled={subscriptionLoading}
                className="w-full"
              >
                {subscriptionLoading
                  ? "Setting up..."
                  : "Set Up Billing Subscription"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Export and Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Button onClick={() => window.print()}>Export Billing Report</Button>
          <Button variant="outline" onClick={fetchBillingData}>
            Refresh Data
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
