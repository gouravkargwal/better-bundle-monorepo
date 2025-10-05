# Attribution Scenarios - Story Documentation

## 📖 **How Attribution Works: A Complete Story**

This document explains each attribution scenario through real-world stories, making it easy to understand what happens in the code and why.

---

## 🎯 **The Complete Customer Journey**

### **Meet Sarah - Our Customer**

Sarah is a 28-year-old marketing professional who loves online shopping. She's browsing a fashion store that uses Better Bundle's recommendation system.

---

## 📱 **Scenario Stories**

### **✅ SCENARIO 1: Direct Recommendation Click → Purchase**

**The Story:**
Sarah is browsing the homepage of a fashion store. She sees a beautiful blue dress recommended to her. She clicks on it, goes to the product page, adds it to her cart, and completes the purchase.

**What Happens in Code:**

```python
# 1. User clicks recommendation
interaction = {
    "extension_type": "phoenix",
    "interaction_type": "recommendation_clicked",
    "product_id": "dress_123",
    "position": 1
}

# 2. User completes purchase
purchase_event = {
    "order_id": "order_456",
    "products": [{"id": "dress_123", "quantity": 1, "price": 89.99}]
}

# 3. Attribution calculation
attribution = {
    "extension": "phoenix",
    "attributed_amount": 89.99,
    "attribution_weight": 1.0
}
```

**Result:** Phoenix gets 100% attribution for the $89.99 purchase.

---

### **✅ SCENARIO 2: Recommendation → Product Page → Quantity Increase**

**The Story:**
Sarah sees a recommended handbag on the homepage. She clicks it, loves it, and decides to buy 3 of them (one for herself, one for her sister, one for her mom).

**What Happens in Code:**

```python
# 1. User clicks recommendation
interaction = {
    "extension_type": "phoenix",
    "interaction_type": "recommendation_clicked",
    "product_id": "handbag_456",
    "position": 2
}

# 2. User increases quantity to 3
purchase_event = {
    "order_id": "order_789",
    "products": [{"id": "handbag_456", "quantity": 3, "price": 45.00}]
}

# 3. Attribution calculation (FIXED!)
# Before: Only $45.00 attributed (unit price)
# After: $135.00 attributed (unit price × quantity)
attribution = {
    "extension": "phoenix",
    "attributed_amount": 135.00,  # 45.00 × 3
    "attribution_weight": 1.0
}
```

**Result:** Phoenix gets 100% attribution for the full $135.00 purchase (all 3 handbags).

---

### **✅ SCENARIO 6: Multiple Recommendations for Same Product**

**The Story:**
Sarah sees a red jacket recommended on the homepage (position 1). She clicks it but doesn't buy. Later, she sees the same jacket recommended on the product page (position 3). She clicks it again and buys it.

**What Happens in Code:**

```python
# 1. First recommendation click
interaction_1 = {
    "extension_type": "phoenix",
    "interaction_type": "recommendation_clicked",
    "product_id": "jacket_789",
    "position": 1,
    "created_at": "2025-01-04T10:00:00Z"
}

# 2. Second recommendation click
interaction_2 = {
    "extension_type": "phoenix",
    "interaction_type": "recommendation_clicked",
    "product_id": "jacket_789",
    "position": 3,
    "created_at": "2025-01-04T10:15:00Z"
}

# 3. Deduplication logic
# Groups by extension + type: "phoenix_clicked"
# Selects best interaction based on:
# - Recency (40%): interaction_2 is newer
# - Position (30%): interaction_1 has better position (1 vs 3)
# - Type (20%): Both are clicked
# - Confidence (10%): Default

# 4. Best interaction selected: interaction_1 (better position wins)
selected_interaction = interaction_1

# 5. Attribution
attribution = {
    "extension": "phoenix",
    "attributed_amount": 120.00,
    "attribution_weight": 1.0
}
```

**Result:** Phoenix gets attribution for the jacket purchase, but only once (no double attribution).

---

### **✅ SCENARIO 11: Refund Attribution**

**The Story:**
Sarah bought a dress based on a recommendation, but it didn't fit well. She returns it and gets a full refund.

**What Happens in Code:**

```python
# 1. Original purchase attribution
original_attribution = {
    "order_id": "order_456",
    "total_revenue": 89.99,
    "attribution_weights": {"phoenix": 1.0},
    "attributed_revenue": {"phoenix": 89.99}
}

# 2. Refund event
refund_event = {
    "refund_id": "refund_123",
    "order_id": "order_456",
    "refund_amount": 89.99
}

# 3. Refund attribution calculation
refund_ratio = 89.99 / 89.99 = 1.0  # Full refund
refund_attribution = {
    "extension": "phoenix",
    "attributed_refund": 89.99,  # 1.0 × 89.99
    "refund_ratio": 1.0
}
```

**Result:** Phoenix's attribution is reduced by $89.99 (full refund).

---

### **✅ SCENARIO 12: Partial Refund Attribution**

**The Story:**
Sarah bought 3 handbags based on a recommendation. She keeps 2 but returns 1 for a partial refund.

**What Happens in Code:**

```python
# 1. Original purchase attribution
original_attribution = {
    "order_id": "order_789",
    "total_revenue": 135.00,  # 3 × $45
    "attribution_weights": {"phoenix": 1.0},
    "attributed_revenue": {"phoenix": 135.00}
}

# 2. Partial refund event
refund_event = {
    "refund_id": "refund_456",
    "order_id": "order_789",
    "refund_amount": 45.00  # 1 handbag returned
}

# 3. Proportional refund attribution
refund_ratio = 45.00 / 135.00 = 0.33  # 33% refund
refund_attribution = {
    "extension": "phoenix",
    "attributed_refund": 45.00,  # 0.33 × 135.00
    "refund_ratio": 0.33
}

# 4. Net attribution
net_attribution = 135.00 - 45.00 = 90.00
```

**Result:** Phoenix's net attribution is $90.00 (keeps attribution for 2 handbags).

---

### **✅ SCENARIO 18: Cross-Device Attribution**

**The Story:**
Sarah is browsing on her phone during lunch break. She sees a beautiful necklace recommended to her. She clicks it but doesn't buy immediately. Later that evening, she opens her laptop and completes the purchase.

**What Happens in Code:**

```python
# 1. Mobile session (phone)
mobile_session = {
    "session_id": "mobile_123",
    "client_id": "shopify_client_abc",
    "device": "mobile",
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "recommendation_clicked",
        "product_id": "necklace_999"
    }]
}

# 2. Desktop session (laptop) - same client_id
desktop_session = {
    "session_id": "desktop_456",
    "client_id": "shopify_client_abc",  # Same client!
    "device": "desktop",
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "product_added_to_cart",
        "product_id": "necklace_999"
    }]
}

# 3. Cross-device session linking
# Code finds existing session with same client_id
cross_device_session = find_session_by_client_id("shopify_client_abc")

# 4. Attribution calculation
# Both interactions are considered for attribution
attribution = {
    "extension": "phoenix",
    "attributed_amount": 199.99,
    "attribution_weight": 1.0,
    "cross_device": True
}
```

**Result:** Phoenix gets attribution for the necklace purchase, even though the recommendation was seen on mobile and purchase was on desktop.

---

### **✅ SCENARIO 19: Client ID vs Session ID Attribution**

**The Story:**
Sarah is browsing anonymously on her phone. She sees a recommendation and clicks it. Later, she logs into her account on her laptop and completes the purchase.

**What Happens in Code:**

```python
# 1. Anonymous mobile session
anonymous_session = {
    "session_id": "anon_123",
    "client_id": "shopify_client_xyz",
    "customer_id": None,  # Anonymous
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "recommendation_clicked",
        "product_id": "shoes_888"
    }]
}

# 2. Logged-in desktop session
logged_in_session = {
    "session_id": "logged_456",
    "client_id": "shopify_client_xyz",  # Same client!
    "customer_id": "customer_789",  # Now logged in
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "product_added_to_cart",
        "product_id": "shoes_888"
    }]
}

# 3. Session linking via client_id
# Code links anonymous session to logged-in session
linked_sessions = link_sessions_by_client_id("shopify_client_xyz")

# 4. Attribution calculation
# Both interactions are considered
attribution = {
    "extension": "phoenix",
    "attributed_amount": 79.99,
    "attribution_weight": 1.0,
    "session_linking": True
}
```

**Result:** Phoenix gets attribution for the shoes purchase, linking the anonymous mobile interaction to the logged-in desktop purchase.

---

### **✅ SCENARIO 7: Cross-Extension Attribution**

**The Story:**
Sarah sees a beautiful watch recommended on the homepage (Atlas extension). She clicks it but doesn't buy. Later, she sees the same watch in her cart recommendations (Phoenix extension). She adds it to cart. Finally, she sees it in a post-purchase email (Apollo extension) and completes the purchase.

**What Happens in Code:**

```python
# 1. Homepage recommendation (Atlas)
atlas_interaction = {
    "extension_type": "atlas",
    "interaction_type": "recommendation_clicked",
    "product_id": "watch_999",
    "position": 1,
    "created_at": "2025-01-04T10:00:00Z"
}

# 2. Cart recommendation (Phoenix)
phoenix_interaction = {
    "extension_type": "phoenix",
    "interaction_type": "recommendation_add_to_cart",
    "product_id": "watch_999",
    "position": 2,
    "created_at": "2025-01-04T10:15:00Z"
}

# 3. Post-purchase email (Apollo)
apollo_interaction = {
    "extension_type": "apollo",
    "interaction_type": "recommendation_clicked",
    "product_id": "watch_999",
    "position": 1,
    "created_at": "2025-01-04T10:30:00Z"
}

# 4. Cross-extension weight calculation
# Phoenix gets highest score (add_to_cart + recent + cart extension)
# Atlas gets medium score (clicked + older + web pixel)
# Apollo gets lowest score (clicked + oldest + post-purchase)

weights = {
    "phoenix": 0.60,  # 60% - most influential
    "atlas": 0.25,    # 25% - initial interest
    "apollo": 0.15    # 15% - final push
}

# 5. Attribution distribution
attribution = {
    "phoenix": 299.99 * 0.60,  # $179.99
    "atlas": 299.99 * 0.25,     # $74.99
    "apollo": 299.99 * 0.15    # $44.99
}
```

**Result:** All three extensions get proportional attribution based on their influence: Phoenix (60%), Atlas (25%), Apollo (15%).

---

### **✅ SCENARIO 8: Session vs Customer Attribution**

**The Story:**
Sarah browses anonymously on her phone, sees a recommendation for a beautiful necklace, and clicks it. Later, she logs into her account on her laptop and completes the purchase.

**What Happens in Code:**

```python
# 1. Anonymous session with recommendation
anonymous_session = {
    "session_id": "anon_123",
    "customer_id": None,  # Anonymous
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "recommendation_clicked",
        "product_id": "necklace_999"
    }]
}

# 2. Customer logs in - session linking
logged_in_session = {
    "session_id": "logged_456",
    "customer_id": "customer_789",  # Now logged in
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "product_added_to_cart",
        "product_id": "necklace_999"
    }]
}

# 3. Customer attribution aggregation
# Code aggregates all interactions across all customer sessions
customer_attribution = {
    "customer_id": "customer_789",
    "total_sessions": 2,
    "total_interactions": 2,
    "products": ["necklace_999"],
    "session_breakdown": {
        "anon_123": {"interaction_count": 1, "extensions": ["phoenix"]},
        "logged_456": {"interaction_count": 1, "extensions": ["phoenix"]}
    }
}

# 4. Attribution calculation
# Both interactions are considered for attribution
attribution = {
    "extension": "phoenix",
    "attributed_amount": 299.99,
    "attribution_weight": 1.0,
    "cross_session": True
}
```

**Result:** Phoenix gets attribution for the necklace purchase, linking the anonymous mobile interaction to the logged-in desktop purchase.

---

### **✅ SCENARIO 9: Long Attribution Window**

**The Story:**
Sarah sees a recommendation for a $2000 laptop. She researches it for 2 weeks, comparing prices and reviews, then finally makes the purchase.

**What Happens in Code:**

```python
# 1. Initial recommendation
recommendation_interaction = {
    "extension_type": "phoenix",
    "interaction_type": "recommendation_clicked",
    "product_id": "laptop_999",
    "created_at": "2025-01-01T10:00:00Z"
}

# 2. Purchase 2 weeks later
purchase_event = {
    "order_id": "order_456",
    "products": [{"id": "laptop_999", "quantity": 1, "price": 2000.00}],
    "purchase_time": "2025-01-15T14:30:00Z"
}

# 3. Attribution window determination
# High-value purchase ($2000) gets extended window (90 days)
attribution_window = "extended"  # 90 days
time_diff = purchase_time - recommendation_time  # 14 days
within_window = time_diff < attribution_window  # True

# 4. Attribution calculation
attribution = {
    "extension": "phoenix",
    "attributed_amount": 2000.00,
    "attribution_weight": 1.0,
    "attribution_window": "extended",
    "time_since_interaction": "14 days"
}
```

**Result:** Phoenix gets attribution for the laptop purchase, even though 14 days passed between recommendation and purchase.

---

### **✅ SCENARIO 10: Multiple Sessions Same Customer**

**The Story:**
Sarah sees a recommendation for a watch in Session A on her phone. She doesn't buy it. Later, she opens Session B on her laptop and sees the same watch again. She adds it to cart and completes the purchase.

**What Happens in Code:**

```python
# 1. Session A (Mobile)
session_a = {
    "session_id": "mobile_123",
    "customer_id": "customer_789",
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "recommendation_clicked",
        "product_id": "watch_888"
    }]
}

# 2. Session B (Desktop)
session_b = {
    "session_id": "desktop_456",
    "customer_id": "customer_789",  # Same customer
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "recommendation_add_to_cart",
        "product_id": "watch_888"
    }]
}

# 3. Cross-session attribution
cross_session_data = {
    "customer_id": "customer_789",
    "product_id": "watch_888",
    "total_sessions": 2,
    "sessions_with_interactions": 2,
    "total_interactions": 2,
    "session_breakdown": {
        "mobile_123": {"interaction_count": 1, "extensions": ["phoenix"]},
        "desktop_456": {"interaction_count": 1, "extensions": ["phoenix"]}
    }
}

# 4. Attribution calculation
# Both sessions contribute to attribution
attribution = {
    "extension": "phoenix",
    "attributed_amount": 199.99,
    "attribution_weight": 1.0,
    "cross_session": True,
    "session_count": 2
}
```

**Result:** Phoenix gets attribution for the watch purchase, considering interactions from both Session A and Session B.

---

### **✅ SCENARIO 14: Payment Failure Attribution**

**The Story:**
Sarah sees a recommendation for a beautiful dress, adds it to cart, but her credit card is declined. She updates her payment method and completes the purchase successfully.

**What Happens in Code:**

```python
# 1. Initial purchase attempt (failed)
failed_purchase = {
    "order_id": "order_123",
    "financial_status": "VOIDED",
    "payment_status": "declined",
    "error_message": "Card declined - insufficient funds"
}

# 2. Payment failure detection
if await _is_payment_failed(context):
    # Payment failed - no attribution given
    return _create_payment_failed_attribution(context)

# 3. Successful purchase attempt
successful_purchase = {
    "order_id": "order_124",
    "financial_status": "PAID",
    "payment_status": "success",
    "products": [{"id": "dress_999", "quantity": 1, "price": 89.99}]
}

# 4. Attribution calculation (only for successful payment)
attribution = {
    "extension": "phoenix",
    "attributed_amount": 89.99,
    "attribution_weight": 1.0,
    "payment_status": "successful"
}
```

**Result:** Phoenix gets attribution only for the successful purchase, not the failed attempt.

---

### **✅ SCENARIO 20: Session Expiration During Journey**

**The Story:**
Sarah sees a recommendation for a laptop, but her session expires while she's researching. She starts a new session and completes the purchase.

**What Happens in Code:**

```python
# 1. Original session with recommendation
original_session = {
    "session_id": "session_123",
    "customer_id": "customer_789",
    "expires_at": "2025-01-04T10:00:00Z",  # Expired
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "recommendation_clicked",
        "product_id": "laptop_999"
    }]
}

# 2. New session after expiry
new_session = {
    "session_id": "session_456",
    "customer_id": "customer_789",  # Same customer
    "interactions": [{
        "extension_type": "phoenix",
        "interaction_type": "product_added_to_cart",
        "product_id": "laptop_999"
    }]
}

# 3. Expired session linking
expired_session = await _find_expired_session_for_linking(
    shop_id, customer_id, browser_session_id, current_time
)

# 4. Session extension and linking
if expired_session:
    # Extend the expired session
    expired_session.expires_at = current_time + session_duration
    expired_session.last_active = current_time

    # Link to new session for attribution
    linked_sessions = [original_session, new_session]

# 5. Attribution calculation
attribution = {
    "extension": "phoenix",
    "attributed_amount": 1999.99,
    "attribution_weight": 1.0,
    "cross_session": True,
    "session_linking": True
}
```

**Result:** Phoenix gets attribution for the laptop purchase, linking the expired session to the new session.

---

### **✅ SCENARIO 27: Fraudulent Attribution Detection**

**The Story:**
A bot tries to inflate attribution by creating fake recommendation clicks. Our system detects this fraud and prevents false attribution.

**What Happens in Code:**

```python
# 1. Bot interaction
bot_interaction = {
    "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "ip_address": "66.249.66.1",  # Known bot IP
    "interaction_type": "recommendation_clicked",
    "created_at": "2025-01-04T10:00:00Z"
}

# 2. Fraud detection
if await _detect_fraudulent_attribution(context):
    # Bot behavior detected
    return _create_fraudulent_attribution(context)

# 3. Fraud detection checks
bot_indicators = ['bot', 'crawler', 'spider', 'scraper']
if any(indicator in user_agent.lower() for indicator in bot_indicators):
    fraud_detected = True

# 4. Attribution result for fraud
fraudulent_attribution = {
    "order_id": "order_999",
    "attributed_revenue": 0.00,  # No attribution given
    "attribution_algorithm": "fraud_detected",
    "fraud_indicators": ["bot_behavior", "suspicious_patterns"]
}
```

**Result:** No attribution is given for fraudulent interactions, protecting the system from manipulation.

---

### **✅ SCENARIO 26: Data Loss Recovery**

**The Story:**
Sarah sees a recommendation, but the system experiences data loss and some interactions are missing. The system detects this and attempts to recover the data to maintain proper attribution.

**What Happens in Code:**

```python
# 1. Data loss detection
if await _detect_data_loss(context):
    logger.warning(f"💾 Data loss detected for order {context.order_id}")
    recovered_data = await _attempt_data_recovery(context)
    if recovered_data:
        context = recovered_data
    else:
        return _create_data_loss_attribution(context)

# 2. Data loss indicators
missing_data_indicators = []
if not context.customer_id and not context.session_id:
    missing_data_indicators.append("missing_customer_session")
if not context.purchase_products:
    missing_data_indicators.append("missing_products")
if context.purchase_amount <= 0:
    missing_data_indicators.append("invalid_purchase_amount")

# 3. Data recovery attempt
recovered_context = await _recover_customer_session_data(context)
recovered_context = await _recover_product_data(recovered_context)
recovered_context = await _recover_interaction_data(recovered_context)

# 4. Attribution result
if recovery_successful:
    attribution = normal_attribution_calculation(recovered_context)
else:
    attribution = {
        "attributed_revenue": 0.00,
        "attribution_algorithm": "data_loss",
        "reason": "Data loss detected - attribution not possible"
    }
```

**Result:** System attempts data recovery and provides attribution if successful, or creates special data loss attribution if recovery fails.

---

### **✅ SCENARIO 28: Attribution Manipulation Detection**

**The Story:**
Sophisticated attackers try to manipulate the attribution system using coordinated attacks, timing manipulation, and interaction inflation. Our system detects these advanced techniques.

**What Happens in Code:**

```python
# 1. Advanced manipulation detection
if await _detect_advanced_manipulation(context):
    return _create_fraudulent_attribution(context)

# 2. Coordinated manipulation check
if await _is_coordinated_manipulation(context):
    # Multiple accounts with similar patterns
    return True

# 3. Timing manipulation check
if await _is_timing_manipulation(context):
    # Unrealistic interaction timing
    return True

# 4. Interaction inflation check
if await _is_interaction_inflation(context):
    # Too many interactions in short time
    return True

# 5. Attribution gaming check
if await _is_attribution_gaming(context):
    # Strategic interaction patterns
    return True

# 6. Fraudulent attribution result
fraudulent_attribution = {
    "attributed_revenue": 0.00,
    "attribution_algorithm": "fraud_detected",
    "fraud_indicators": ["coordinated_manipulation", "timing_anomalies", "interaction_inflation"]
}
```

**Result:** Advanced manipulation techniques are detected and prevented, protecting the attribution system from sophisticated attacks.

---

### **✅ SCENARIO 33: Anonymous to Customer Conversion**

**The Story:**
Sarah browses anonymously, sees recommendations, then creates an account and logs in. We need to link her anonymous sessions to her new customer account for proper attribution.

**What Happens in Code:**

```python
# 1. Anonymous to customer conversion
conversion_result = await handle_anonymous_to_customer_conversion(
    customer_id="customer_789",
    shop_id="shop_123",
    conversion_session_id="session_456"
)

# 2. Find anonymous sessions
anonymous_sessions = await _find_anonymous_sessions_for_conversion(
    customer_id, shop_id, conversion_session_id
)

# 3. Calculate conversion confidence
for session in anonymous_sessions:
    confidence = await _calculate_conversion_confidence(
        session, conversion_session
    )
    if confidence >= min_confidence_threshold:
        likely_sessions.append(session)

# 4. Link anonymous sessions
linked_sessions = await _link_anonymous_sessions_to_customer(
    customer_id, shop_id, anonymous_sessions
)

# 5. Update conversion session attribution
await _update_conversion_session_attribution(
    conversion_session_id, customer_id, linked_sessions
)

# 6. Conversion result
conversion_result = {
    "success": True,
    "conversion_type": "anonymous_to_customer",
    "linked_sessions": ["session_123", "session_456"],
    "attribution_updated": True
}
```

**Result:** Anonymous sessions are successfully linked to the customer account, maintaining attribution continuity from anonymous browsing to logged-in purchase.

---

### **✅ SCENARIO 34: Multiple Devices Same Customer**

**The Story:**
Sarah uses her phone to browse and see recommendations, then switches to her laptop to complete the purchase. We need to link sessions across devices for proper attribution.

**What Happens in Code:**

```python
# 1. Multi-device session handling
device_result = await handle_multiple_devices_same_customer(
    customer_id="customer_789",
    shop_id="shop_123",
    device_sessions=["session_mobile_123", "session_desktop_456"]
)

# 2. Link sessions across devices
linked_sessions = await _link_device_sessions(
    customer_id, shop_id, device_session_objects
)

# 3. Extract device information
device_info = _extract_device_info(session)
# Returns: {"type": "mobile", "os": "ios", "user_agent": "..."}

# 4. Aggregate cross-device attribution
attribution_summary = await _aggregate_cross_device_attribution(
    customer_id, shop_id, linked_sessions
)

# 5. Device breakdown
device_breakdown = {
    "mobile_ios": {
        "device_type": "mobile",
        "os": "ios",
        "sessions": ["session_mobile_123"],
        "interactions": 5
    },
    "desktop_macos": {
        "device_type": "desktop",
        "os": "macos",
        "sessions": ["session_desktop_456"],
        "interactions": 3
    }
}

# 6. Multi-device result
multi_device_result = {
    "success": True,
    "scenario": "multiple_devices_same_customer",
    "linked_sessions": ["session_mobile_123", "session_desktop_456"],
    "attribution_summary": attribution_summary
}
```

**Result:** Sessions across multiple devices are successfully linked, providing complete attribution for Sarah's multi-device shopping journey.

---

## 🔧 **Technical Implementation Details**

### **How Deduplication Works (Scenario 6)**

```python
def _deduplicate_product_interactions(interactions):
    """
    Story: When Sarah sees the same product recommended multiple times,
    we need to pick the best interaction to avoid double attribution.
    """

    # 1. Group interactions by extension and type
    groups = {
        "phoenix_clicked": [interaction1, interaction2],
        "phoenix_add_to_cart": [interaction3]
    }

    # 2. For each group, select the best interaction
    for group_key, group_interactions in groups.items():
        if len(group_interactions) > 1:
            # Select best based on scoring
            best = select_best_interaction(group_interactions)
        else:
            best = group_interactions[0]

    # 3. Prioritize add_to_cart over clicks
    if has_add_to_cart:
        filter_out_click_interactions()

    return deduplicated_interactions
```

### **How Cross-Device Linking Works (Scenario 18)**

```python
def _find_cross_device_session(shop_id, client_id):
    """
    Story: When Sarah switches from phone to laptop,
    we use her Shopify client_id to link the sessions.
    """

    # Find active session with same client_id
    session = find_session_by_client_id(client_id)

    if session:
        logger.info(f"🔗 Cross-device session found: {session.id}")
        return session

    return None
```

### **How Refund Attribution Works (Scenarios 11-12)**

```python
def _calculate_proportional_refund_attribution(original_attribution, refund):
    """
    Story: When Sarah gets a refund, we need to reverse
    the attribution proportionally.
    """

    # Calculate refund ratio
    refund_ratio = refund.amount / original_attribution.total_revenue

    # Apply ratio to original weights
    refund_weights = {
        extension: weight * refund_ratio
        for extension, weight in original_attribution.weights.items()
    }

    return refund_weights
```

---

## 📊 **Attribution Flow Diagram**

```
User Journey → Interactions → Attribution Engine → Revenue Tracking

1. Sarah browses homepage
   ↓
2. Sees recommendation (Phoenix)
   ↓
3. Clicks recommendation
   ↓
4. Goes to product page
   ↓
5. Adds to cart
   ↓
6. Completes purchase
   ↓
7. Attribution Engine calculates:
   - Finds all interactions for product
   - Deduplicates multiple recommendations
   - Links cross-device sessions
   - Calculates attribution weights
   ↓
8. Revenue tracking:
   - Phoenix gets attribution
   - Commission calculated
   - Analytics updated
```

---

## 🎯 **Key Benefits of Our Implementation**

### **1. Accurate Attribution**

- ✅ No double attribution for same product
- ✅ Cross-device attribution works
- ✅ Refund attribution is proportional

### **2. Fair Commission Calculation**

- ✅ Merchants pay only for actual influence
- ✅ Refunds reduce commission proportionally
- ✅ Cross-device influence is recognized

### **3. Robust System**

- ✅ Handles edge cases gracefully
- ✅ Prevents fraud and manipulation
- ✅ Scales with high traffic

---

## 🚀 **What's Next**

### **Implemented Scenarios (9/43)**

- ✅ Scenario 1: Direct recommendation clicks
- ✅ Scenario 2: Quantity increase attribution
- ✅ Scenario 6: Multiple recommendations deduplication
- ✅ Scenario 11: Refund attribution
- ✅ Scenario 12: Partial refund attribution
- ✅ Scenario 18: Cross-device attribution
- ✅ Scenario 19: Client ID session linking
- ✅ Basic homepage, product page, cart recommendations
- ✅ Collection page recommendations

### **Next Priority Scenarios**

- 🔄 Scenario 7: Cross-extension attribution
- 🔄 Scenario 8: Session vs customer attribution
- 🔄 Scenario 9: Configurable attribution windows
- 🔄 Scenario 14: Payment failure handling
- 🔄 Scenario 20: Session expiration handling

---

_This documentation is maintained by the development team and updated as new scenarios are implemented._
