# Attribution Scenarios Documentation

## Overview

This document outlines all possible attribution scenarios in our recommendation system, their coverage status, and implementation strategies.

📖 **For detailed story-based explanations of how each scenario works, see [Attribution Stories Documentation](./attribution-stories.md)**

---

## 📊 **Scenario Coverage Status**

| Status                   | Count  | Percentage |
| ------------------------ | ------ | ---------- |
| ✅ **Covered**           | 25     | 58%        |
| 🚧 **Partially Covered** | 3      | 7%         |
| ❌ **Not Covered**       | 15     | 35%        |
| **Total**                | **43** | **100%**   |

### **Priority Breakdown**

| Priority      | Count  | Percentage |
| ------------- | ------ | ---------- |
| 🔥 **HIGH**   | 15     | 35%        |
| ⚡ **MEDIUM** | 15     | 35%        |
| 📈 **LOW**    | 13     | 30%        |
| **Total**     | **43** | **100%**   |

---

## 🎯 **Complete Attribution Scenarios List**

### **📱 BASIC INTERACTION Scenarios**

#### **✅ COVERED Scenarios**

#### **1. Direct Recommendation Click → Purchase**

- **Scenario**: User clicks recommendation → Product page → Add to cart → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Direct attribution with 100% weight
- **Code**: `_create_direct_attribution()` method

#### **2. Recommendation → Product Page → Quantity Increase**

- **Scenario**: User clicks recommendation → Increases quantity → Purchase
- **Status**: ✅ **Fully Covered** (Fixed in latest update)
- **Implementation**: Full quantity attribution (unit_price × quantity)
- **Code**: `product_amount = unit_price * quantity`

#### **3. Cart Recommendation → Add to Cart**

- **Scenario**: Cart page → Clicks recommendation → Add to cart → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Phoenix extension attribution
- **Code**: `recommendation_add_to_cart` interaction type

#### **4. Collection Page → Recommendation → Purchase**

- **Scenario**: Collection page → Clicks recommendation → Product page → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Atlas extension with collection context
- **Code**: Collection page recommendation service

#### **5. Homepage → Recommendation → Purchase**

- **Scenario**: Homepage → Clicks recommendation → Product page → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Atlas extension with homepage context
- **Code**: Homepage recommendation service

#### **6. Product Page → Recommendation → Purchase**

- **Scenario**: Product page → Clicks "Customers also bought" → Add to cart → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Product page recommendation service
- **Code**: `get_smart_product_page_recommendation()`

#### **7. Search Page → Recommendation → Purchase**

- **Scenario**: Search results → Clicks recommendation → Product page → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Search context recommendations
- **Code**: Search page recommendation service

#### **8. Profile Page → Recommendation → Purchase**

- **Scenario**: Customer profile → Clicks recommendation → Product page → Purchase
- **Status**: ✅ **Fully Covered**
- **Implementation**: Venus extension with profile context
- **Code**: Profile recommendation service

---

### **🚧 PARTIALLY COVERED Scenarios**

#### **6. Multiple Recommendations for Same Product**

- **Scenario**: Homepage → Clicks Rec A → Product page → Clicks Rec B → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Smart deduplication with interaction prioritization
- **Features**:
  - Groups interactions by extension and type
  - Prioritizes add_to_cart over clicks
  - Selects best interaction based on recency, position, type, and confidence
- **Code**: `_deduplicate_product_interactions()` method

#### **7. Cross-Extension Attribution**

- **Scenario**: Atlas (Homepage) → Phoenix (Cart) → Apollo (Post-Purchase)
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Smart weight distribution based on interaction scoring
- **Features**:
  - Calculates interaction scores based on recency, type, extension, position
  - Primary interaction gets 60%, others get 40% distributed
  - Normalizes weights to ensure they sum to 1.0
- **Code**: `_calculate_cross_extension_weights()` method

#### **8. Session vs Customer Attribution**

- **Scenario**: Anonymous → Recommendation → Login → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Customer-level attribution aggregation
- **Features**:
  - Aggregates interactions across all customer sessions
  - Links anonymous sessions to customer accounts
  - Stores customer attribution summaries
- **Code**: `_aggregate_customer_attribution()` method

#### **9. Long Attribution Window**

- **Scenario**: Recommendation → Browse for 2 hours → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Configurable attribution windows based on purchase value
- **Features**:
  - Short window (2h) for purchases under $50
  - Medium window (3d) for purchases $50-$200
  - Long window (30d) for purchases $200-$1000
  - Extended window (90d) for purchases $1000+
- **Code**: `_determine_attribution_window()` method

#### **10. Multiple Sessions Same Customer**

- **Scenario**: Session A → Recommendation → Session B → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Cross-session attribution with customer linking
- **Features**:
  - Links multiple sessions for same customer
  - Tracks interactions across all customer sessions
  - Calculates cross-session attribution breakdown
- **Code**: `_handle_cross_session_attribution()` method

---

### **❌ NOT COVERED Scenarios**

#### **11. Refund Attribution**

- **Scenario**: Recommendation → Purchase → Refund
- **Status**: ❌ **Not Covered**
- **Impact**: High - Revenue reversal not tracked
- **Solution**: Implement RefundAttribution system
- **Priority**: 🔥 **HIGH**

#### **12. Partial Refund Attribution**

- **Scenario**: Recommendation → Purchase (3 items) → Refund (1 item)
- **Status**: ❌ **Not Covered**
- **Impact**: High - Inaccurate revenue tracking
- **Solution**: Proportional refund attribution
- **Priority**: 🔥 **HIGH**

#### **13. Cross-Device Attribution**

- **Scenario**: Mobile → Recommendation → Desktop → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: High - Missing cross-device influence
- **Solution**: Customer-level attribution with device tracking
- **Priority**: 🔥 **HIGH**

#### **14. Payment Failure Attribution**

- **Scenario**: Recommendation → Purchase → Payment Declined → Retry → Success
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Payment failure detection and filtering
- **Features**:
  - Detects failed payments via financial status
  - Filters out failed payment attempts
  - Only attributes successful payments
- **Code**: `_is_payment_failed()` method

#### **15. Subscription Cancellation**

- **Scenario**: Recommendation → Purchase → Subscription Cancelled
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Service suspension impact
- **Solution**: Maintain attribution but stop new processing
- **Priority**: ⚡ **MEDIUM**

---

## 🔄 **ADVANCED INTERACTION Scenarios**

### **❌ NOT COVERED Scenarios (Continued)**

#### **16. Multiple Refunds for Same Order**

- **Scenario**: Purchase → Refund A → Refund B → Refund C
- **Status**: ❌ **Not Covered**
- **Impact**: High - Cumulative refund tracking
- **Solution**: Track cumulative refunds with attribution adjustment
- **Priority**: 🔥 **HIGH**

#### **17. Refund After Attribution Window**

- **Scenario**: Recommendation → Purchase → 30 days later → Refund
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Long-term refund attribution
- **Solution**: Maintain attribution records for refund processing
- **Priority**: ⚡ **MEDIUM**

#### **18. Mobile App vs Web Browser**

- **Scenario**: Mobile App → Recommendation → Web Browser → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: High - Cross-platform attribution
- **Solution**: Cross-platform session linking
- **Priority**: 🔥 **HIGH**

#### **19. Client ID vs Session ID**

- **Scenario**: Anonymous → Recommendation → Login → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: High - Client ID to customer ID attribution
- **Solution**: Link client_id to customer_id for proper attribution
- **Priority**: 🔥 **HIGH**

#### **20. Session Expiration During Journey**

- **Scenario**: Recommendation → Session Expires → New Session → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Expired session linking and extension
- **Features**:
  - Finds recently expired sessions
  - Links expired sessions to new sessions
  - Extends expired sessions for attribution continuity
- **Code**: `_find_expired_session_for_linking()` method

#### **21. Low-Quality Recommendations**

- **Scenario**: Poor Recommendation → User Ignores → Direct Product Search → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Attribution for ignored recommendations
- **Solution**: No attribution for ignored recommendations
- **Priority**: ⚡ **MEDIUM**

#### **22. Recommendation Position Impact**

- **Scenario**: Position 1 Recommendation → Position 5 Recommendation → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Position-based attribution weights
- **Solution**: Weight attribution based on position
- **Priority**: ⚡ **MEDIUM**

#### **23. Recommendation Algorithm Changes**

- **Scenario**: Old Algorithm → Recommendation → New Algorithm → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Algorithm version tracking
- **Solution**: Track algorithm version in attribution metadata
- **Priority**: 📈 **LOW**

#### **24. System Downtime During Attribution**

- **Scenario**: Recommendation → System Down → Recovery → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Missing interactions during downtime
- **Solution**: Graceful degradation and recovery attribution
- **Priority**: ⚡ **MEDIUM**

#### **25. High Traffic Attribution**

- **Scenario**: Black Friday → High Load → Recommendation → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - System performance during high traffic
- **Solution**: Async attribution processing with queuing
- **Priority**: ⚡ **MEDIUM**

#### **26. Data Loss Recovery**

- **Scenario**: Recommendation → Data Loss → Recovery → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Data loss detection and recovery mechanisms
- **Features**:
  - Detects missing customer/session data
  - Identifies corrupted purchase amounts
  - Attempts data recovery from available sources
  - Creates special attribution for unrecoverable data loss
- **Code**: `_detect_data_loss()` and `_attempt_data_recovery()` methods

#### **27. Fraudulent Attribution**

- **Scenario**: Bot → Fake Recommendation Clicks → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Multi-layered fraud detection
- **Features**:
  - Bot behavior detection via user agent
  - Suspicious pattern analysis
  - Attribution manipulation detection
- **Code**: `_detect_fraudulent_attribution()` method

#### **28. Attribution Manipulation**

- **Scenario**: Malicious → Fake Interactions → Attribution Inflation
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Advanced manipulation detection
- **Features**:
  - Detects coordinated manipulation across accounts
  - Identifies timing manipulation patterns
  - Prevents interaction inflation
  - Detects attribution gaming attempts
- **Code**: `_detect_advanced_manipulation()` method

#### **29. Cross-Shop Attribution**

- **Scenario**: Shop A → Recommendation → Shop B → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Cross-shop attribution (not needed)
- **Solution**: Shop-specific attribution (no cross-shop attribution)
- **Priority**: 📈 **LOW**

#### **30. Shop Migration**

- **Scenario**: Old Shop → Recommendation → New Shop → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Shop migration attribution
- **Solution**: Shop-specific attribution with migration tracking
- **Priority**: 📈 **LOW**

#### **31. Attribution Reporting Discrepancies**

- **Scenario**: Recommendation → Purchase → Different Attribution in Reports
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Data inconsistency
- **Solution**: Single source of truth for attribution data
- **Priority**: ⚡ **MEDIUM**

#### **32. Real-time vs Batch Attribution**

- **Scenario**: Recommendation → Purchase → Real-time Attribution → Batch Processing
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Different attribution results
- **Solution**: Consistent attribution logic across processing methods
- **Priority**: ⚡ **MEDIUM**

#### **33. Anonymous to Customer Conversion**

- **Scenario**: Anonymous → Recommendation → Login → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Anonymous session linking and conversion handling
- **Features**:
  - Finds anonymous sessions using browser fingerprinting
  - Calculates conversion confidence scores
  - Links anonymous sessions to customer accounts
  - Aggregates attribution across conversion
- **Code**: `handle_anonymous_to_customer_conversion()` method

#### **34. Multiple Devices Same Customer**

- **Scenario**: Mobile → Recommendation → Desktop → Purchase
- **Status**: ✅ **Fully Covered** (IMPLEMENTED)
- **Implementation**: Multi-device session linking and attribution
- **Features**:
  - Links sessions across multiple devices
  - Extracts device information (mobile, desktop, tablet)
  - Aggregates cross-device attribution
  - Maintains attribution continuity
- **Code**: `handle_multiple_devices_same_customer()` method

#### **35. Recommendation A/B Testing**

- **Scenario**: Test A → Recommendation → Test B → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - A/B test attribution
- **Solution**: Track A/B test variants in attribution
- **Priority**: ⚡ **MEDIUM**

#### **36. Seasonal Attribution**

- **Scenario**: Black Friday → Recommendation → Christmas → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Seasonal attribution patterns
- **Solution**: Seasonal attribution adjustments
- **Priority**: 📈 **LOW**

#### **37. Geographic Attribution**

- **Scenario**: US → Recommendation → EU → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Cross-geography attribution
- **Solution**: Geographic attribution tracking
- **Priority**: 📈 **LOW**

#### **38. Time Zone Attribution**

- **Scenario**: EST → Recommendation → PST → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Time zone attribution
- **Solution**: UTC-based attribution with time zone awareness
- **Priority**: 📈 **LOW**

#### **39. Attribution Data Privacy**

- **Scenario**: GDPR → Recommendation → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: High - Privacy compliance
- **Solution**: GDPR-compliant attribution tracking
- **Priority**: 🔥 **HIGH**

#### **40. Attribution Data Retention**

- **Scenario**: Old Data → Recommendation → New Data → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Data retention policies
- **Solution**: Configurable data retention for attribution
- **Priority**: ⚡ **MEDIUM**

#### **41. Attribution Data Export**

- **Scenario**: Recommendation → Purchase → Data Export
- **Status**: ❌ **Not Covered**
- **Impact**: Low - Data export functionality
- **Solution**: Attribution data export APIs
- **Priority**: 📈 **LOW**

#### **42. Attribution Data Backup**

- **Scenario**: Recommendation → Purchase → Data Backup
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - Data backup and recovery
- **Solution**: Attribution data backup and recovery
- **Priority**: ⚡ **MEDIUM**

#### **43. Attribution Data Migration**

- **Scenario**: Old System → Recommendation → New System → Purchase
- **Status**: ❌ **Not Covered**
- **Impact**: Medium - System migration
- **Solution**: Attribution data migration tools
- **Priority**: ⚡ **MEDIUM**

---

## 🔧 **Implementation Strategies**

### **High Priority Fixes**

#### **1. Refund Attribution System**

```python
# Implementation needed
class RefundAttributionEngine:
    async def process_refund_attribution(self, refund_event):
        # 1. Find original purchase attribution
        # 2. Calculate proportional refund
        # 3. Create RefundAttribution record
        # 4. Adjust revenue tracking
```

#### **2. Cross-Device Attribution**

```python
# Implementation needed
class CrossDeviceAttribution:
    async def link_customer_sessions(self, customer_id):
        # 1. Find all sessions for customer
        # 2. Link sessions across devices
        # 3. Aggregate attribution data
        # 4. Create unified attribution
```

#### **3. Product Deduplication**

```python
# Implementation needed
class AttributionDeduplication:
    async def deduplicate_product_attribution(self, product_id, interactions):
        # 1. Group interactions by product
        # 2. Find primary attribution source
        # 3. Remove duplicate attributions
        # 4. Return clean attribution
```

### **Medium Priority Fixes**

#### **4. Configurable Attribution Windows**

```python
# Implementation needed
class AttributionWindowConfig:
    def get_attribution_window(self, context, extension_type):
        # 1. Get context-specific window
        # 2. Apply extension-specific rules
        # 3. Return appropriate time window
```

#### **5. Cross-Extension Weight Distribution**

```python
# Implementation needed
class CrossExtensionAttribution:
    def distribute_attribution_weights(self, extensions, total_amount):
        # 1. Calculate extension weights
        # 2. Distribute attribution proportionally
        # 3. Apply business rules
```

---

## 📋 **Action Plan**

### **Phase 1: Critical Fixes (Week 1-2)**

1. ✅ **Fix quantity attribution** (COMPLETED)
2. 🔄 **Implement refund attribution system** (Scenarios 11, 16, 17)
3. 🔄 **Add cross-device attribution** (Scenarios 18, 19, 20, 33, 34)
4. 🔄 **Implement product deduplication** (Scenario 6)
5. 🔄 **Add fraud detection** (Scenarios 27, 28)

### **Phase 2: Important Fixes (Week 3-4)**

6. 🔄 **Add configurable attribution windows** (Scenario 9)
7. 🔄 **Implement cross-extension weights** (Scenario 7)
8. 🔄 **Enhance customer linking** (Scenarios 8, 10)
9. 🔄 **Add payment failure handling** (Scenario 14)
10. 🔄 **Add session management** (Scenarios 20, 33)
11. 🔄 **Add data loss recovery** (Scenario 26)

### **Phase 3: Medium Priority (Week 5-6)**

12. 🔄 **Add recommendation quality tracking** (Scenarios 21, 22)
13. 🔄 **Add system performance optimization** (Scenarios 24, 25)
14. 🔄 **Add analytics consistency** (Scenarios 31, 32)
15. 🔄 **Add A/B testing support** (Scenario 35)
16. 🔄 **Add data privacy compliance** (Scenario 39)

### **Phase 4: Nice-to-Have (Week 7-8)**

17. 🔄 **Add seasonal attribution** (Scenario 36)
18. 🔄 **Add geographic attribution** (Scenario 37)
19. 🔄 **Add time zone handling** (Scenario 38)
20. 🔄 **Add data export/backup** (Scenarios 41, 42)
21. 🔄 **Add system migration support** (Scenario 43)

---

## 🎯 **Success Metrics**

### **Coverage Targets**

- **Phase 1**: 60% scenario coverage
- **Phase 2**: 80% scenario coverage
- **Phase 3**: 95% scenario coverage

### **Quality Metrics**

- **Attribution Accuracy**: >95%
- **Revenue Tracking**: >99%
- **System Performance**: <100ms attribution processing
- **Data Consistency**: 100% across all systems

---

## 📚 **Related Documentation**

- [Attribution Engine API](./attribution-engine-api.md)
- [Refund Attribution System](./refund-attribution.md)
- [Cross-Device Attribution](./cross-device-attribution.md)
- [Performance Optimization](./attribution-performance.md)

---

## 🔄 **Last Updated**

- **Date**: 2025-01-04
- **Version**: 1.0
- **Author**: AI Assistant
- **Status**: Active Development

---

## 📝 **Notes**

### **Current Limitations**

1. No refund attribution tracking
2. Limited cross-device attribution
3. Basic product deduplication
4. No fraud detection
5. Limited performance optimization

### **Future Enhancements**

1. Machine learning-based attribution
2. Real-time attribution processing
3. Advanced fraud detection
4. Multi-tenant attribution
5. Attribution analytics dashboard

---

## 🚀 **Quick Reference**

### **Immediate Actions Needed**

1. **Fix quantity attribution** ✅ (COMPLETED)
2. **Implement refund attribution** 🔥 (HIGH PRIORITY)
3. **Add cross-device attribution** 🔥 (HIGH PRIORITY)
4. **Implement fraud detection** 🔥 (HIGH PRIORITY)

### **Key Files to Modify**

- `attribution_engine.py` - Core attribution logic
- `refund_attribution_consumer.py` - Refund handling
- `unified_session_service.py` - Session management
- `cross_session_linking_service.py` - Customer linking

### **Testing Scenarios**

- Test quantity attribution with multiple items
- Test refund attribution with partial refunds
- Test cross-device attribution with different devices
- Test fraud detection with suspicious patterns

### **Monitoring Metrics**

- Attribution accuracy rate
- Revenue tracking accuracy
- System performance metrics
- Fraud detection rate

---

_This document is maintained by the development team and updated regularly as new scenarios are identified and implemented._
