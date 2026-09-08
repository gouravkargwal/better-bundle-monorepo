// Design tokens for BetterBundle
// Centralized colors, spacing, radii, and surface styles so the UI stays
// consistent and inline hex values don't multiply across components.

/** @jsxImportSource react */

// ── Brand palette ──────────────────────────────────────────────────────────

export const brand = {
  indigoStart: "#667eea",
  indigoEnd: "#764ba2",
};

// ── Surface backgrounds ────────────────────────────────────────────────────

export const surfaces = {
  success: {
    bg: "#F0FDF4",
    border: "#BBF7D0",
    strongBorder: "#22C55E",
    text: "#166534",
  },
  warning: {
    bg: "#FEF3C7",
    border: "#FCD34D",
    strongBorder: "#F59E0B",
    text: "#92400E",
  },
  error: {
    bg: "#FEF2F2",
    border: "#FECACA",
    strongBorder: "#F87171",
    text: "#991B1B",
  },
  info: {
    bg: "#EFF6FF",
    border: "#BFDBFE",
    strongBorder: "#3B82F6",
    text: "#1E40AF",
  },
  neutral: {
    bg: "#FAFAFA",
    border: "#E5E7EB",
    text: "#6B7280",
  },
  muted: {
    bg: "#F5F3FF",
    border: "#DDD6FE",
  },
  slate: {
    bg: "#F8FAFC",
    border: "#E2E8F0",
  },
};

// ── Component radii ────────────────────────────────────────────────────────

export const radii = {
  sm: "6px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "9999px",
};

// ── Shadows ────────────────────────────────────────────────────────────────

export const shadows = {
  card: "0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)",
  elevated:
    "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
};
