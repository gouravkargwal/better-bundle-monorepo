import { useState, useCallback } from "react";
import {
  Popover,
  Button,
  Card,
  TextField,
  InlineStack,
  BlockStack,
  Text,
  Box,
} from "@shopify/polaris";
import { CalendarIcon } from "@shopify/polaris-icons";

interface DateRange {
  startDate: string;
  endDate: string;
}

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onDateChange: (range: DateRange) => void;
  maxDate?: string;
}

const presets = [
  { label: "Today", value: "today", days: 0 },
  { label: "Last 7 days", value: "last_7_days", days: 7 },
  { label: "Last 30 days", value: "last_30_days", days: 30 },
  { label: "Last 90 days", value: "last_90_days", days: 90 },
  { label: "This month", value: "this_month", days: null },
  { label: "Last month", value: "last_month", days: null },
];

export function DateRangePicker({
  startDate,
  endDate,
  onDateChange,
  maxDate,
}: DateRangePickerProps) {
  const [popoverActive, setPopoverActive] = useState(false);
  const [tempStartDate, setTempStartDate] = useState(startDate);
  const [tempEndDate, setTempEndDate] = useState(endDate);

  const togglePopoverActive = useCallback(
    () => setPopoverActive((active) => !active),
    [],
  );

  const formatDateForDisplay = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const handlePresetClick = (preset: (typeof presets)[0]) => {
    const end = new Date();
    let start = new Date();

    if (preset.value === "today") {
      start = new Date();
    } else if (preset.value === "this_month") {
      start = new Date(end.getFullYear(), end.getMonth(), 1);
    } else if (preset.value === "last_month") {
      start = new Date(end.getFullYear(), end.getMonth() - 1, 1);
      end.setDate(0); // Last day of previous month
    } else if (preset.days !== null) {
      start.setDate(end.getDate() - preset.days);
    }

    const newStartDate = start.toISOString().split("T")[0];
    const newEndDate = end.toISOString().split("T")[0];

    setTempStartDate(newStartDate);
    setTempEndDate(newEndDate);
  };

  const handleApply = () => {
    onDateChange({
      startDate: tempStartDate,
      endDate: tempEndDate,
    });
    setPopoverActive(false);
  };

  const handleCancel = () => {
    setTempStartDate(startDate);
    setTempEndDate(endDate);
    setPopoverActive(false);
  };

  const activator = (
    <Button
      onClick={togglePopoverActive}
      disclosure={popoverActive ? "up" : "down"}
      icon={CalendarIcon}
      size="large"
    >
      {formatDateForDisplay(startDate)} - {formatDateForDisplay(endDate)}
    </Button>
  );

  return (
    <Popover
      active={popoverActive}
      activator={activator}
      onClose={togglePopoverActive}
      preferredAlignment="right"
      preferredPosition="below"
    >
      <div style={{ width: "420px" }}>
        <Card>
          <BlockStack gap="400">
            {/* Quick Presets */}
            <Box padding="400" paddingBlockEnd="0">
              <BlockStack gap="300">
                <Text as="h3" variant="headingSm" fontWeight="semibold">
                  Quick select
                </Text>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "8px",
                  }}
                >
                  {presets.map((preset) => (
                    <Button
                      key={preset.value}
                      onClick={() => handlePresetClick(preset)}
                      size="slim"
                    >
                      {preset.label}
                    </Button>
                  ))}
                </div>
              </BlockStack>
            </Box>

            {/* Custom Date Inputs */}
            <Box padding="400" paddingBlockStart="200">
              <BlockStack gap="300">
                <Text as="h3" variant="headingSm" fontWeight="semibold">
                  Custom range
                </Text>
                <InlineStack gap="300" align="start">
                  <div style={{ flex: 1 }}>
                    <TextField
                      label="Start date"
                      type="date"
                      value={tempStartDate}
                      onChange={setTempStartDate}
                      autoComplete="off"
                      max={tempEndDate}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <TextField
                      label="End date"
                      type="date"
                      value={tempEndDate}
                      onChange={setTempEndDate}
                      autoComplete="off"
                      min={tempStartDate}
                      max={maxDate || new Date().toISOString().split("T")[0]}
                    />
                  </div>
                </InlineStack>
              </BlockStack>
            </Box>

            {/* Action Buttons */}
            <Box padding="400" paddingBlockStart="200">
              <InlineStack align="end" gap="200">
                <Button onClick={handleCancel}>Cancel</Button>
                <Button variant="primary" onClick={handleApply}>
                  Apply
                </Button>
              </InlineStack>
            </Box>
          </BlockStack>
        </Card>
      </div>
    </Popover>
  );
}
