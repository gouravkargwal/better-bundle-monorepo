# BetterBundle App Structure

This document outlines the industry-standard folder structure and code organization for the BetterBundle application.

## 📁 Folder Structure

```
app/
├── core/                    # Core application infrastructure
│   ├── config/             # Configuration files
│   ├── database/           # Database setup and configuration
│   └── errors/             # Custom error classes
├── features/               # Feature-based modules
│   ├── bundle-analysis/    # Bundle analysis feature
│   │   ├── services/BundleAnalyticsService.ts
│   │   └── index.ts
│   ├── data-collection/    # Data collection feature
│   │   ├── services/DataCollectionService.ts
│   │   ├── services/PrivateAppDataCollectionService.ts
│   │   └── index.ts
│   └── data-validation/    # Data validation feature
│       ├── DataValidationService.ts
│       └── index.ts
├── shared/                 # Shared components and utilities
│   ├── components/         # Reusable UI components
│   ├── services/           # Shared services
│   └── types/              # Shared type definitions
├── hooks/                  # Custom React hooks
├── types/                  # Global type definitions
├── utils/                  # Utility functions
├── constants/              # Application constants
└── routes/                 # Remix routes
    ├── api/                # API endpoints
    │   ├── analysis/       # Bundle analysis APIs
    │   ├── widget/         # Widget APIs
    │   └── config/         # Configuration APIs
    ├── app/                # App pages
    ├── webhooks/           # Webhook handlers
    │   ├── orders/         # Order webhooks
    │   └── app/            # App webhooks
    └── auth/               # Authentication routes
```

## 🏗️ Architecture Principles

### **1. Feature-Based Organization**

- Each feature is self-contained with its own components, services, and types
- Features can be easily added, removed, or modified independently
- Clear separation of concerns between different business domains

### **2. Shared Resources**

- Common components, services, and utilities are shared across features
- Centralized type definitions and constants
- Consistent error handling and database access patterns

### **3. Core Infrastructure**

- Database configuration and connection management
- Custom error classes for consistent error handling
- Application-wide configuration

## 📦 Key Files

### **Types (`app/types/index.ts`)**

- Centralized type definitions for the entire application
- Includes interfaces for bundles, orders, validation results, etc.

### **Constants (`app/constants/index.ts`)**

- Application-wide constants for configuration, error messages, and UI settings
- Prevents magic numbers and strings throughout the codebase

### **Database (`app/core/database/prisma.server.ts`)**

- Centralized Prisma client configuration
- Handles development vs production connection management

### **Error Handling (`app/core/errors/AppError.ts`)**

- Custom error classes for different types of application errors
- Consistent error structure and handling patterns

### **Custom Hooks (`app/hooks/useAnalysis.ts`)**

- Reusable React hooks for common functionality
- Encapsulates complex state management logic

## 🔄 Migration Benefits

### **Before (Monolithic Structure)**

```
app/
├── components/             # Mixed concerns
├── services/              # All services in one place
├── routes/                # All routes mixed together
└── db.server.ts           # Simple database file
```

### **After (Modular Structure)**

```
app/
├── features/              # Feature-based organization
│   ├── bundle-analysis/   # Bundle analysis logic
│   ├── data-collection/   # Data collection logic
│   └── data-validation/   # Data validation logic
├── shared/                # Reusable components
├── core/                  # Infrastructure
├── hooks/                 # Custom hooks
└── types/                 # Centralized types
```

## 🚀 Benefits

1. **Maintainability**: Easier to find and modify specific functionality
2. **Scalability**: New features can be added without affecting existing code
3. **Reusability**: Shared components and utilities reduce code duplication
4. **Type Safety**: Centralized types ensure consistency across the application
5. **Testing**: Features can be tested in isolation
6. **Team Collaboration**: Multiple developers can work on different features simultaneously

## 📊 Bundle Analysis Limitations

### **Current Implementation (MVP)**

- **Bundle Size**: Currently supports only bundles of size 2 (product pairs)
- **Algorithm**: Uses simple pair extraction for computational efficiency
- **Revenue Calculation**: Now calculates actual revenue based on product prices instead of placeholder values

### **Future Enhancements**

- **Larger Bundles**: Support for bundles of size 3+ using Apriori or FP-Growth algorithms
- **Advanced Analytics**: More sophisticated bundle discovery and scoring
- **Performance Optimization**: Caching and incremental analysis for large datasets

## 📝 Usage Examples

### **Importing Types**

```typescript
import type { Bundle, AnalysisState, ErrorState } from "../types";
```

### **Using Constants**

```typescript
import { ANALYSIS_CONFIG, ERROR_MESSAGES } from "../constants";
```

### **Using Custom Hooks**

```typescript
import { useAnalysis } from "../hooks/useAnalysis";
```

### **Using Shared Components**

```typescript
import { DashboardState } from "../shared/components/DashboardState";
```

### **Using Feature Services**

```typescript
import { DataValidationService } from "../features/data-validation";
```

This structure follows industry best practices and makes the codebase more maintainable, scalable, and developer-friendly.
