import { useState, useCallback, useEffect } from "react";
import { useSearchParams, useNavigate, useLocation } from "@remix-run/react";
import type { DashboardData } from "../types/dashboard.types";

export function useDashboard(dashboardData: DashboardData | null) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [selectedTab, setSelectedTab] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const handleTabChange = useCallback((selectedTabIndex: number) => {
    setSelectedTab(selectedTabIndex);
  }, []);

  const handleDateChange = useCallback(
    (range: { startDate: string; endDate: string }) => {
      setIsLoading(true);
      const params = new URLSearchParams(searchParams);
      params.set("startDate", range.startDate);
      params.set("endDate", range.endDate);

      // Navigate to the current pathname with new date parameters
      navigate(`${location.pathname}?${params.toString()}`, { replace: true });
    },
    [navigate, searchParams, location.pathname],
  );

  // Reset loading state when data changes
  useEffect(() => {
    setIsLoading(false);
  }, [dashboardData]);

  return {
    selectedTab,
    isLoading,
    handleTabChange,
    handleDateChange,
  };
}
