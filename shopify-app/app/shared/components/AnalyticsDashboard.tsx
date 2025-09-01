/**
 * Analytics Dashboard Component
 * Shows recommendation performance, engagement metrics, and billing data
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
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
  Cell
} from 'recharts';

interface TrackingEvent {
  id: string;
  eventType: string;
  sessionId: string;
  trackingId: string;
  userId?: string;
  timestamp: string;
  metadata: any;
}

interface ShopAnalytics {
  id: string;
  totalRecommendationsDisplayed: number;
  totalRecommendationsClicked: number;
  totalRecommendationsAddedToCart: number;
  totalRecommendationsPurchased: number;
  totalRevenueAttributed: number;
  totalWidgetInteractions: number;
  lastUpdated: string;
}

interface AnalyticsData {
  events: TrackingEvent[];
  analytics: ShopAnalytics;
  eventTypeBreakdown: Array<{ eventType: string; _count: { eventType: number } }>;
  dailyEvents: Array<{ date: string; event_type: string; count: number }>;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export default function AnalyticsDashboard() {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState(30);

  useEffect(() => {
    fetchAnalyticsData();
  }, [timeRange]);

  const fetchAnalyticsData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/tracking?days=${timeRange}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch analytics data');
      }

      const data = await response.json();
      setAnalyticsData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  const calculateConversionRate = (numerator: number, denominator: number) => {
    if (denominator === 0) return 0;
    return ((numerator / denominator) * 100).toFixed(2);
  };

  const getEventTypeLabel = (eventType: string) => {
    const labels: Record<string, string> = {
      'recommendation_displayed': 'Recommendations Displayed',
      'recommendation_clicked': 'Recommendations Clicked',
      'recommendation_added_to_cart': 'Added to Cart',
      'recommendation_purchased': 'Purchased',
      'widget_interaction': 'Widget Interactions',
    };
    return labels[eventType] || eventType;
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
        <div className="text-red-600 mb-4">Error loading analytics: {error}</div>
        <Button onClick={fetchAnalyticsData}>Retry</Button>
      </div>
    );
  }

  if (!analyticsData) {
    return <div>No analytics data available</div>;
  }

  const { analytics, eventTypeBreakdown, dailyEvents } = analyticsData;

  // Prepare chart data
  const eventTypeData = eventTypeBreakdown.map(item => ({
    name: getEventTypeLabel(item.eventType),
    value: item._count.eventType,
  }));

  const dailyData = dailyEvents.reduce((acc: any[], event) => {
    const existingDate = acc.find(item => item.date === event.date);
    if (existingDate) {
      existingDate[event.event_type] = event.count;
    } else {
      const newDate = { date: event.date };
      newDate[event.event_type] = event.count;
      acc.push(newDate);
    }
    return acc;
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
          <p className="text-gray-600">Track recommendation performance and user engagement</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={timeRange === 7 ? "default" : "outline"}
            onClick={() => setTimeRange(7)}
          >
            7 Days
          </Button>
          <Button
            variant={timeRange === 30 ? "default" : "outline"}
            onClick={() => setTimeRange(30)}
          >
            30 Days
          </Button>
          <Button
            variant={timeRange === 90 ? "default" : "outline"}
            onClick={() => setTimeRange(90)}
          >
            90 Days
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recommendations Displayed</CardTitle>
            <Badge variant="secondary">Total</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(analytics.totalRecommendationsDisplayed)}
            </div>
            <p className="text-xs text-muted-foreground">
              Last updated: {new Date(analytics.lastUpdated).toLocaleDateString()}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Click Rate</CardTitle>
            <Badge variant="secondary">Conversion</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {calculateConversionRate(
                analytics.totalRecommendationsClicked,
                analytics.totalRecommendationsDisplayed
              )}%
            </div>
            <p className="text-xs text-muted-foreground">
              {formatNumber(analytics.totalRecommendationsClicked)} clicks
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Add to Cart Rate</CardTitle>
            <Badge variant="secondary">Conversion</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {calculateConversionRate(
                analytics.totalRecommendationsAddedToCart,
                analytics.totalRecommendationsClicked
              )}%
            </div>
            <p className="text-xs text-muted-foreground">
              {formatNumber(analytics.totalRecommendationsAddedToCart)} added
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Revenue Attributed</CardTitle>
            <Badge variant="secondary">Total</Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(analytics.totalRevenueAttributed)}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatNumber(analytics.totalRecommendationsPurchased)} purchases
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="events">Event Breakdown</TabsTrigger>
          <TabsTrigger value="trends">Daily Trends</TabsTrigger>
          <TabsTrigger value="billing">Billing Data</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Event Type Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={eventTypeData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {eventTypeData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Display → Click</span>
                    <span className="font-medium">
                      {calculateConversionRate(
                        analytics.totalRecommendationsClicked,
                        analytics.totalRecommendationsDisplayed
                      )}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{
                        width: `${calculateConversionRate(
                          analytics.totalRecommendationsClicked,
                          analytics.totalRecommendationsDisplayed
                        )}%`,
                      }}
                    ></div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Click → Add to Cart</span>
                    <span className="font-medium">
                      {calculateConversionRate(
                        analytics.totalRecommendationsAddedToCart,
                        analytics.totalRecommendationsClicked
                      )}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-green-600 h-2 rounded-full"
                      style={{
                        width: `${calculateConversionRate(
                          analytics.totalRecommendationsAddedToCart,
                          analytics.totalRecommendationsClicked
                        )}%`,
                      }}
                    ></div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Add to Cart → Purchase</span>
                    <span className="font-medium">
                      {calculateConversionRate(
                        analytics.totalRecommendationsPurchased,
                        analytics.totalRecommendationsAddedToCart
                      )}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-purple-600 h-2 rounded-full"
                      style={{
                        width: `${calculateConversionRate(
                          analytics.totalRecommendationsPurchased,
                          analytics.totalRecommendationsAddedToCart
                        )}%`,
                      }}
                    ></div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="events" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Event Type Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={eventTypeData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Daily Event Trends</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dailyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="recommendation_displayed"
                    stroke="#8884d8"
                    name="Displayed"
                  />
                  <Line
                    type="monotone"
                    dataKey="recommendation_clicked"
                    stroke="#82ca9d"
                    name="Clicked"
                  />
                  <Line
                    type="monotone"
                    dataKey="recommendation_added_to_cart"
                    stroke="#ffc658"
                    name="Added to Cart"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="billing" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Revenue Attribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span>Total Revenue Attributed</span>
                    <span className="text-2xl font-bold text-green-600">
                      {formatCurrency(analytics.totalRevenueAttributed)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Total Purchases</span>
                    <span className="text-xl font-medium">
                      {formatNumber(analytics.totalRecommendationsPurchased)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Average Order Value</span>
                    <span className="text-lg">
                      {analytics.totalRecommendationsPurchased > 0
                        ? formatCurrency(
                            analytics.totalRevenueAttributed / analytics.totalRecommendationsPurchased
                          )
                        : formatCurrency(0)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Usage Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span>Widget Interactions</span>
                    <span className="text-xl font-medium">
                      {formatNumber(analytics.totalWidgetInteractions)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Recommendations per Session</span>
                    <span className="text-lg">
                      {analytics.totalRecommendationsDisplayed > 0
                        ? (analytics.totalRecommendationsDisplayed / Math.max(1, eventTypeBreakdown.length)).toFixed(2)
                        : '0'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Engagement Rate</span>
                    <span className="text-lg">
                      {analytics.totalRecommendationsDisplayed > 0
                        ? `${((analytics.totalRecommendationsClicked / analytics.totalRecommendationsDisplayed) * 100).toFixed(1)}%`
                        : '0%'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Export and Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Button onClick={() => window.print()}>
            Export Report
          </Button>
          <Button variant="outline" onClick={fetchAnalyticsData}>
            Refresh Data
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
