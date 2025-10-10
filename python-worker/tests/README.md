# Attribution Scenarios Test Suite

This comprehensive test suite allows you to test all attribution scenarios without requiring frontend interaction. It provides unit tests, integration tests, performance tests, and realistic mock data generation.

## 🚀 Quick Start

### 1. Run All Tests

```bash
cd python-worker/tests
python run_tests.py
```

### 2. Run Specific Scenario

```bash
python run_tests.py --scenario 6
```

### 3. Generate Test Data

```bash
python run_tests.py --generate-data
```

### 4. Run Performance Tests

```bash
python run_tests.py --performance
```

### 5. List Available Scenarios

```bash
python run_tests.py --list
```

## 📋 Available Scenarios

| #   | Scenario                                  | Status | Description                                                          |
| --- | ----------------------------------------- | ------ | -------------------------------------------------------------------- |
| 6   | Multiple Recommendations for Same Product | ✅     | Tests deduplication of multiple recommendations for the same product |
| 7   | Cross-Extension Attribution               | ✅     | Tests attribution across multiple extensions                         |
| 8   | Session vs Customer Attribution           | ✅     | Tests linking sessions to customer attribution                       |
| 9   | Long Attribution Window                   | ✅     | Tests configurable attribution windows                               |
| 10  | Multiple Sessions Same Customer           | ✅     | Tests multiple sessions for same customer                            |
| 11  | Refund Attribution                        | ✅     | Tests refund attribution processing                                  |
| 12  | Partial Refund Attribution                | ✅     | Tests partial refund attribution                                     |
| 14  | Payment Failure Attribution               | ✅     | Tests payment failure detection and handling                         |
| 15  | Subscription Cancellation                 | ✅     | Tests subscription cancellation handling                             |
| 17  | Cross-Shop Attribution                    | ✅     | Tests cross-shop attribution scenarios                               |
| 18  | Cross-Device Attribution                  | ✅     | Tests cross-device session linking                                   |
| 19  | Client ID vs Session ID Attribution       | ✅     | Tests client ID vs session ID attribution                            |
| 20  | Session Expiration During Journey         | ✅     | Tests session expiration handling                                    |
| 21  | Low-Quality Recommendations               | ✅     | Tests low-quality recommendation detection                           |
| 22  | Recommendation Timing                     | ✅     | Tests recommendation timing analysis                                 |
| 26  | Data Loss Recovery                        | ✅     | Tests data loss detection and recovery                               |
| 27  | Fraudulent Attribution Detection          | ✅     | Tests fraudulent attribution detection                               |
| 28  | Attribution Manipulation Detection        | ✅     | Tests attribution manipulation detection                             |
| 33  | Anonymous to Customer Conversion          | ✅     | Tests anonymous to customer conversion                               |
| 34  | Multiple Devices Same Customer            | ✅     | Tests multiple devices for same customer                             |

## 🧪 Test Files

### Core Test Files

- **`test_attribution_scenarios.py`** - Comprehensive unit tests for all scenarios
- **`test_runner.py`** - Main test runner with scenario execution
- **`test_data_generator.py`** - Realistic test data generation
- **`run_tests.py`** - Command-line interface for running tests

### Test Categories

#### 1. Unit Tests

Individual scenario tests that verify specific functionality:

```python
async def test_scenario_6_multiple_recommendations(self):
    """Test Scenario 6: Multiple recommendations for same product"""
    # Test deduplication logic
    # Test best interaction selection
```

#### 2. Integration Tests

End-to-end tests that verify complete flows:

```python
async def test_full_attribution_flow(self):
    """Test complete attribution flow with multiple scenarios"""
    # Test entire attribution calculation process
```

#### 3. Performance Tests

Tests for scalability and performance:

```python
async def test_attribution_performance(self):
    """Test attribution calculation performance"""
    # Test with large datasets
    # Measure processing time
```

## 📊 Test Data Generation

The test suite includes a comprehensive data generator that creates realistic test data:

### Generated Data Types

- **Customer Data**: Realistic customer profiles with purchase history
- **Shop Data**: Multi-shop scenarios with different configurations
- **Product Data**: Diverse product catalogs with pricing and inventory
- **Session Data**: Cross-device sessions with realistic timestamps
- **Interaction Data**: User behavior patterns and recommendation interactions
- **Order Data**: Complete order scenarios with line items
- **Attribution Contexts**: Scenario-specific attribution contexts

### Example Generated Data

```json
{
  "customers": [
    {
      "customer_id": "customer_1234",
      "email": "customer123@example.com",
      "first_name": "Sarah",
      "last_name": "Smith",
      "total_orders": 15,
      "total_spent": "1250.50",
      "loyalty_tier": "gold"
    }
  ],
  "scenarios": {
    "payment_failure": {
      "order_id": "order_payment_failure_5678",
      "metadata": {
        "financial_status": "VOIDED",
        "payment_status": "declined"
      }
    }
  }
}
```

## 🔧 Test Configuration

### Environment Setup

```bash
# Install dependencies
pip install pytest asyncio

# Set up environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/python-worker"
```

### Test Execution Options

```bash
# Run with verbose output
python run_tests.py --scenario 6 -v

# Run specific test categories
python -m pytest test_attribution_scenarios.py::TestAttributionScenarios::test_scenario_6_multiple_recommendations -v

# Run with coverage
python -m pytest --cov=app.domains.billing.services.attribution_engine test_attribution_scenarios.py
```

## 📈 Test Results

### Success Criteria

Each test validates:

- ✅ **Functionality**: Core logic works correctly
- ✅ **Edge Cases**: Handles unusual scenarios
- ✅ **Performance**: Meets performance requirements
- ✅ **Error Handling**: Graceful error handling
- ✅ **Data Integrity**: Maintains data consistency

### Sample Output

```
🧪 Testing Scenario 6: Multiple Recommendations for Same Product
✅ Scenario 6 Result: {
  "original_count": 3,
  "deduplicated_count": 2,
  "best_interaction_type": "recommendation_add_to_cart",
  "success": true
}

📊 TEST SUMMARY REPORT
============================================================
Total Tests: 13
Passed: 12
Failed: 1
Success Rate: 92.3%
```

## 🐛 Debugging Tests

### Common Issues

1. **Import Errors**: Ensure PYTHONPATH includes the project root
2. **Async Issues**: Use `asyncio.run()` for async test execution
3. **Mock Data**: Verify mock data matches expected schemas
4. **Performance**: Adjust performance thresholds based on your system

### Debug Mode

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run specific test with debug
python run_tests.py --scenario 6 --debug
```

## 🔄 Continuous Integration

### GitHub Actions Integration

```yaml
name: Attribution Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run attribution tests
        run: cd python-worker/tests && python run_tests.py
```

## 📚 Advanced Usage

### Custom Test Scenarios

```python
# Create custom test scenario
async def test_custom_scenario(self):
    """Test custom attribution scenario"""
    context = self.create_mock_context(
        "custom_scenario",
        metadata={"custom_field": "custom_value"}
    )
    result = await self.attribution_engine.calculate_attribution(context)
    assert result.attribution_algorithm == "custom"
```

### Performance Benchmarking

```python
# Benchmark attribution calculation
import time
start_time = time.time()
result = await attribution_engine.calculate_attribution(context)
end_time = time.time()
assert (end_time - start_time) < 1.0  # Should complete in < 1 second
```

### Data Validation

```python
# Validate test data integrity
def validate_attribution_result(result):
    assert result.order_id is not None
    assert result.attributed_revenue >= 0
    assert result.attribution_algorithm in ["normal", "cross_shop", "low_quality"]
```

## 🎯 Best Practices

1. **Test Isolation**: Each test should be independent
2. **Realistic Data**: Use realistic mock data that reflects production scenarios
3. **Performance Monitoring**: Track performance metrics over time
4. **Error Scenarios**: Test both success and failure cases
5. **Documentation**: Keep test documentation up to date

## 📞 Support

For questions or issues with the test suite:

1. Check the test logs for detailed error messages
2. Verify all dependencies are installed
3. Ensure the project structure is correct
4. Review the test data generation for accuracy

---

**Happy Testing! 🧪✨**
