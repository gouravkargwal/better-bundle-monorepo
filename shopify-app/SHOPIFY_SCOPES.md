# BetterBundle Shopify API Scopes

## Overview

This document outlines all the Shopify API scopes required for the complete BetterBundle system functionality.

## Required Scopes

### **1. Product Management**

```bash
read_products,write_products
```

**Purpose:**

- Read product data for recommendations
- Update product bundles and pricing
- Manage product relationships
- Access product analytics

### **2. Order Management**

```bash
read_orders,write_orders
```

**Purpose:**

- Process order webhooks for revenue attribution
- Read order details for tracking
- Update order attributes with tracking data
- Access order analytics

### **3. Customer Management**

```bash
read_customers,write_customers
```

**Purpose:**

- Access customer data for personalization
- Update customer preferences
- Track customer behavior
- Build customer profiles for recommendations

### **4. Inventory Management**

```bash
read_inventory,write_inventory
```

**Purpose:**

- Check product availability
- Update inventory levels
- Manage bundle stock
- Prevent overselling

### **5. Analytics & Marketing**

```bash
read_analytics,read_marketing_events,write_marketing_events
```

**Purpose:**

- Access store analytics
- Track marketing campaign performance
- Measure recommendation effectiveness
- Generate performance reports

### **6. Pricing & Discounts**

```bash
read_price_rules,write_price_rules,read_discounts,write_discounts
```

**Purpose:**

- Create bundle discounts
- Manage pricing rules
- Apply promotional offers
- Track discount performance

### **7. Theme & Content**

```bash
read_script_tags,write_script_tags,read_themes,write_themes,read_content,write_content
```

**Purpose:**

- Install tracking scripts
- Customize theme for recommendations
- Manage app widgets
- Update store content

### **8. Localization**

```bash
read_locales,write_locales,read_currency,write_currency
```

**Purpose:**

- Support multiple languages
- Handle currency conversion
- Localize recommendations
- Adapt to regional preferences

### **9. Billing & Payments**

```bash
read_payment_schedules,write_payment_schedules,read_usage_charges,write_usage_charges,read_recurring_application_charges,write_recurring_application_charges
```

**Purpose:**

- Create billing subscriptions
- Process usage charges
- Manage payment schedules
- Handle commission collection

## Scope Categories

### **Essential Scopes (Core Functionality)**

- `read_products,write_products`
- `read_orders,write_orders`
- `read_customers,write_customers`
- `read_inventory,write_inventory`

### **Billing Scopes (Payment Collection)**

- `read_recurring_application_charges,write_recurring_application_charges`
- `read_usage_charges,write_usage_charges`
- `read_payment_schedules,write_payment_schedules`

### **Analytics Scopes (Performance Tracking)**

- `read_analytics`
- `read_marketing_events,write_marketing_events`

### **Customization Scopes (User Experience)**

- `read_script_tags,write_script_tags`
- `read_themes,write_themes`
- `read_content,write_content`

### **Localization Scopes (International Support)**

- `read_locales,write_locales`
- `read_currency,write_currency`

### **Pricing Scopes (Bundle Management)**

- `read_price_rules,write_price_rules`
- `read_discounts,write_discounts`

## Implementation

### **1. Configuration File**

```toml
# shopify.app.toml
[access_scopes]
scopes = "write_products,read_products,read_orders,write_orders,read_customers,write_customers,read_inventory,write_inventory,read_analytics,read_marketing_events,write_marketing_events,read_price_rules,write_price_rules,read_discounts,write_discounts,read_script_tags,write_script_tags,read_themes,write_themes,read_content,write_content,read_locales,write_locales,read_currency,write_currency,read_payment_schedules,write_payment_schedules,read_usage_charges,write_usage_charges,read_recurring_application_charges,write_recurring_application_charges"
```

### **2. App Installation**

When users install the app, they'll see a permission request screen showing:

- **Data Access**: Products, orders, customers, inventory
- **Billing**: Subscription and usage charges
- **Analytics**: Store performance data
- **Customization**: Theme and content modifications

### **3. Scope Validation**

```typescript
// Validate required scopes are granted
const requiredScopes = [
  "read_products",
  "write_products",
  "read_orders",
  "write_orders",
  "read_customers",
  "write_customers",
  "read_inventory",
  "write_inventory",
  "read_recurring_application_charges",
  "write_recurring_application_charges",
  "read_usage_charges",
  "write_usage_charges",
];

const missingScopes = requiredScopes.filter(
  (scope) => !session.scope.includes(scope),
);
if (missingScopes.length > 0) {
  throw new Error(`Missing required scopes: ${missingScopes.join(", ")}`);
}
```

## Security Considerations

### **1. Principle of Least Privilege**

- Only request scopes that are actually needed
- Explain why each scope is required
- Provide clear documentation

### **2. Data Protection**

- Encrypt sensitive data
- Follow GDPR compliance
- Implement data retention policies
- Secure API communications

### **3. User Transparency**

- Clear permission explanations
- Easy scope management
- Transparent data usage
- Simple deauthorization process

## User Experience

### **1. Installation Flow**

1. User clicks "Install App"
2. Shopify shows permission request
3. User reviews and approves scopes
4. App is installed with full functionality

### **2. Permission Explanations**

- **Products**: "Access to read and update product information for recommendations"
- **Orders**: "Track orders to attribute revenue and calculate commissions"
- **Customers**: "Personalize recommendations based on customer behavior"
- **Billing**: "Process performance-based commission payments"

### **3. Scope Management**

- Users can review granted permissions
- Easy to revoke specific scopes
- Clear impact of scope changes
- Graceful degradation if scopes are removed

## Troubleshooting

### **Common Issues**

#### **1. Missing Billing Scopes**

```bash
Error: Missing billing permissions
Solution: Ensure read_recurring_application_charges and write_recurring_application_charges are granted
```

#### **2. Analytics Access Denied**

```bash
Error: Cannot access analytics data
Solution: Verify read_analytics scope is included
```

#### **3. Theme Modification Failed**

```bash
Error: Cannot modify theme
Solution: Check read_themes and write_themes permissions
```

### **Debug Commands**

```bash
# Check current scopes
curl -X GET "https://your-shop.myshopify.com/admin/api/2024-01/shop.json" \
  -H "X-Shopify-Access-Token: your-access-token"

# Validate scope access
curl -X GET "https://your-shop.myshopify.com/admin/api/2024-01/products.json" \
  -H "X-Shopify-Access-Token: your-access-token"
```

## Best Practices

### **1. Scope Organization**

- Group related scopes together
- Use consistent naming conventions
- Document scope dependencies
- Maintain scope hierarchy

### **2. Error Handling**

- Graceful degradation for missing scopes
- Clear error messages
- Fallback functionality
- User guidance for resolution

### **3. Testing**

- Test with minimal scopes
- Validate scope combinations
- Mock scope restrictions
- Test permission changes

## Future Considerations

### **1. Scope Evolution**

- Monitor Shopify API changes
- Update scope requirements
- Maintain backward compatibility
- Plan for new features

### **2. Compliance**

- Stay updated with privacy regulations
- Implement data minimization
- Regular scope audits
- User consent management

---

_This scope configuration ensures BetterBundle has all necessary permissions while maintaining security and user privacy._
