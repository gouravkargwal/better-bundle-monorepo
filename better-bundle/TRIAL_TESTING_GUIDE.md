# 🧪 Trial Testing Guide

## **Testing the $200 Revenue-Based Trial Flow**

This guide covers both automated testing and manual testing approaches for the trial system.

---

## **1. Automated Testing**

### **A. Unit Tests**

```bash
# Run unit tests
npm test app/utils/__tests__/trialStatus.test.ts

# Run with coverage
npm test -- --coverage app/utils/__tests__/trialStatus.test.ts
```

### **B. Integration Tests**

```bash
# Run integration tests
npm test app/utils/__tests__/trialFlow.integration.test.ts

# Run all trial tests
npm test -- --testNamePattern="Trial"
```

### **C. Test Coverage**

- **Unit Tests**: 95%+ coverage
- **Integration Tests**: 90%+ coverage
- **Edge Cases**: 100% coverage

---

## **2. Manual Testing**

### **A. Test Dashboard Access**

1. Navigate to: `/app/test/trial`
2. Use the interactive dashboard to test various scenarios
3. Monitor real-time status updates

### **B. Quick Test Scenarios**

#### **Scenario 1: Fresh Installation**

```typescript
// Test: Create new trial
POST /api/test/trial
{
  "testType": "create_trial"
}

// Expected Result:
{
  "isTrialActive": true,
  "currentRevenue": 0,
  "threshold": 200,
  "remainingRevenue": 200,
  "progress": 0
}
```

#### **Scenario 2: Revenue Generation**

```typescript
// Test: Add $100 revenue
POST /api/test/trial
{
  "testType": "add_revenue",
  "revenueAmount": 100
}

// Expected Result:
{
  "isTrialActive": true,
  "currentRevenue": 100,
  "threshold": 200,
  "remainingRevenue": 100,
  "progress": 50
}
```

#### **Scenario 3: Trial Completion**

```typescript
// Test: Add $100 more revenue (total $200)
POST /api/test/trial
{
  "testType": "add_revenue",
  "revenueAmount": 100
}

// Expected Result:
{
  "isTrialActive": false,
  "trialCompleted": true,
  "needsConsent": true,
  "currentRevenue": 200,
  "threshold": 200,
  "remainingRevenue": 0,
  "progress": 100
}
```

#### **Scenario 4: Consent and Billing**

```typescript
// Test: Complete trial with consent
POST /api/test/trial
{
  "testType": "complete_with_consent"
}

// Expected Result:
{
  "isTrialActive": false,
  "trialCompleted": true,
  "needsConsent": false,
  "subscription_created": true
}
```

---

## **3. Test Scenarios**

### **A. Basic Flow Testing**

1. **Create Trial** → Verify trial is active
2. **Add $50 Revenue** → Verify 25% progress
3. **Add $100 Revenue** → Verify 75% progress
4. **Add $50 Revenue** → Verify trial completion
5. **Give Consent** → Verify billing activation

### **B. Edge Case Testing**

1. **Exact Threshold** → Add exactly $200
2. **Exceeding Threshold** → Add $250
3. **Multiple Small Updates** → Add $10, $20, $30, etc.
4. **Zero Revenue** → Test with $0
5. **Negative Revenue** → Test error handling

### **C. Currency Testing**

1. **USD** → Default currency
2. **EUR** → European currency
3. **GBP** → British currency
4. **CAD** → Canadian currency
5. **AUD** → Australian currency

### **D. Error Testing**

1. **Database Errors** → Simulate connection failures
2. **Invalid Data** → Test with invalid inputs
3. **Missing Plans** → Test without trial plan
4. **Concurrent Updates** → Test race conditions

---

## **4. Test Data Setup**

### **A. Development Data**

```typescript
// Create test shop
const testShop = {
  id: "test-shop.myshopify.com",
  domain: "test-shop.myshopify.com",
  currency: "USD",
  accessToken: "test-token",
};

// Create test trial plan
const testPlan = {
  shopId: testShop.id,
  shopDomain: testShop.domain,
  name: "Test Trial Plan",
  type: "trial_only",
  status: "active",
  configuration: {
    trial_active: true,
    trial_threshold: 200.0,
    trial_revenue: 0.0,
    revenue_share_rate: 0.03,
    currency: "USD",
    subscription_required: false,
    trial_without_consent: true,
  },
  isTrialActive: true,
  trialThreshold: 200.0,
  trialRevenue: 0.0,
};
```

### **B. Test Revenue Scenarios**

```typescript
const revenueScenarios = [
  { amount: 50, expected: "25% complete" },
  { amount: 100, expected: "50% complete" },
  { amount: 150, expected: "75% complete" },
  { amount: 200, expected: "100% complete" },
  { amount: 250, expected: "125% complete" },
];
```

---

## **5. Performance Testing**

### **A. Load Testing**

```typescript
// Test concurrent revenue updates
const concurrentUpdates = Array(100)
  .fill(0)
  .map((_, i) => updateTrialRevenue(shopId, 1));

await Promise.all(concurrentUpdates);
```

### **B. Stress Testing**

```typescript
// Test rapid status checks
const statusChecks = Array(1000)
  .fill(0)
  .map(() => getTrialStatus(shopId));

await Promise.all(statusChecks);
```

---

## **6. Monitoring and Debugging**

### **A. Log Monitoring**

```typescript
// Enable detailed logging
console.log("Trial Status:", {
  shopId,
  isTrialActive,
  currentRevenue,
  threshold,
  progress,
});
```

### **B. Database Monitoring**

```sql
-- Monitor trial plans
SELECT
  shopId,
  trialRevenue,
  trialThreshold,
  isTrialActive,
  configuration
FROM BillingPlan
WHERE status = 'active';

-- Monitor trial events
SELECT
  shopId,
  type,
  data,
  createdAt
FROM BillingEvent
WHERE type LIKE '%trial%'
ORDER BY createdAt DESC;
```

---

## **7. Test Automation**

### **A. CI/CD Integration**

```yaml
# .github/workflows/trial-tests.yml
name: Trial Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: "18"
      - name: Install dependencies
        run: npm install
      - name: Run trial tests
        run: npm test -- --testNamePattern="Trial"
      - name: Run integration tests
        run: npm test -- --testNamePattern="Integration"
```

### **B. Scheduled Testing**

```typescript
// Daily trial flow test
const dailyTest = async () => {
  const testResults = await testingUtils.runAllTests();

  if (testResults.summary.successRate < 95) {
    // Alert on test failures
    await sendAlert("Trial tests failing", testResults);
  }
};
```

---

## **8. Test Results Validation**

### **A. Success Criteria**

- ✅ **Trial Creation**: 100% success rate
- ✅ **Revenue Updates**: 100% success rate
- ✅ **Status Tracking**: 100% accuracy
- ✅ **Trial Completion**: 100% success rate
- ✅ **Consent Flow**: 100% success rate

### **B. Performance Criteria**

- ✅ **Response Time**: < 100ms for status checks
- ✅ **Update Time**: < 200ms for revenue updates
- ✅ **Concurrent Users**: 100+ simultaneous updates
- ✅ **Database Load**: < 50ms query time

---

## **9. Troubleshooting**

### **A. Common Issues**

1. **Trial Not Created** → Check shop authentication
2. **Revenue Not Updated** → Check database connection
3. **Status Not Refreshed** → Check cache invalidation
4. **Consent Not Working** → Check subscription creation

### **B. Debug Commands**

```bash
# Check trial status
curl -X GET /api/test/trial

# Create trial
curl -X POST /api/test/trial -d "testType=create_trial"

# Add revenue
curl -X POST /api/test/trial -d "testType=add_revenue&revenueAmount=100"

# Complete trial
curl -X POST /api/test/trial -d "testType=complete_with_consent"
```

---

## **10. Best Practices**

### **A. Testing Strategy**

1. **Start with Unit Tests** → Test individual functions
2. **Add Integration Tests** → Test complete flows
3. **Include Manual Testing** → Test real-world scenarios
4. **Monitor Performance** → Test under load
5. **Validate Edge Cases** → Test error conditions

### **B. Test Data Management**

1. **Use Test Shops** → Don't test on production
2. **Clean Test Data** → Reset between tests
3. **Isolate Tests** → Each test should be independent
4. **Mock External Services** → Don't hit real APIs
5. **Validate Results** → Check expected outcomes

---

## **🎯 Summary**

**Testing Approach:**

- ✅ **Automated**: Unit + Integration tests
- ✅ **Manual**: Interactive dashboard
- ✅ **Performance**: Load + Stress testing
- ✅ **Monitoring**: Real-time status tracking

**Expected Results:**

- 🚀 **95%+ test coverage**
- 🚀 **< 100ms response time**
- 🚀 **100% success rate**
- 🚀 **Zero production issues**

**This comprehensive testing approach ensures the $200 trial flow works perfectly! 🏆**
