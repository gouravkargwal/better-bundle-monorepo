# Python Worker - Exhaustive Detailed Documentation

This document covers every file in the Python worker project with exact code details, including function signatures, line numbers, SQLAlchemy queries, external API calls, Kafka messages, return value structures, and known bugs.

---

## Table of Contents

1. [API Routes](#1-api-routes)
2. [Request/Response Models](#2-requestresponse-models)
3. [Controllers](#3-controllers)
4. [Services](#4-services)
5. [Kafka Consumers](#5-kafka-consumers)
6. [Recommendation Engine](#6-recommendation-engine)
7. [Repositories](#7-repositories)
8. [Core Infrastructure](#8-core-infrastructure)
9. [Database Models](#9-database-models)

---

## 1. API Routes

### 1.1 Auth Routes

**File:** `app/routes/auth_routes.py`

```python
router = APIRouter(prefix="/api/auth", tags=["Authentication"])
```

#### `POST /api/auth/generate-token`
- **Function:** `generate_access_token(request: GenerateTokenRequest)` (line 14)
- **Response Model:** `GenerateTokenResponse`
- **No auth required** (this endpoint generates the token)
- **Delegates to:** `auth_controller.generate_shop_token(request)`

#### `POST /api/auth/refresh-token`
- **Function:** `refresh_access_token(request: RefreshTokenRequest)` (line 19)
- **Response Model:** `RefreshTokenResponse`
- **No auth required**
- **Delegates to:** `auth_controller.refresh_access_token(request)`

---

### 1.2 Session Routes

**File:** `app/routes/session_routes.py`

```python
router = APIRouter(prefix="/api/session", tags=["Session Management"])
```

#### Helper Functions

```python
def extract_ip_address(request: Request) -> str | None  # line 20
```
- Checks `X-Forwarded-For` header (first IP in chain), then `X-Real-IP`, then `request.client.host`

```python
def extract_user_agent(request: Request) -> str | None  # line 42
```
- Returns `request.headers.get("User-Agent")`

#### `POST /api/session/get-or-create-session`
- **Function:** `get_or_create_session(http_request, request: SessionRequest, shop_info)` (line 48)
- **Response Model:** `SessionResponse`
- **Auth:** `Depends(get_shop_authorization)` -- JWT Bearer token
- **Logic:**
  - If `request.ip_address is True` (boolean flag), extracts IP from headers (line 55-56)
  - If `request.user_agent is True`, extracts User-Agent from headers (line 59-60)
  - Delegates to `session_controller.get_or_create_session(request, shop_info)`
  - Returns `SessionResponse(success=True, message="Session created successfully", data=session_data)`

#### `POST /api/session/get-session-and-recommendations`
- **Function:** `get_session_and_recommendations(http_request, request: SessionAndRecommendationsRequest, shop_info)` (line 86)
- **Response Model:** `SessionAndRecommendationsResponse`
- **Auth:** `Depends(get_shop_authorization)`
- **Delegates to:** `recommendation_controller.get_recommendations_with_session(http_request, request, shop_info)`

---

### 1.3 Recommendation Routes

**File:** `app/routes/recommendation_routes.py`

```python
router = APIRouter(prefix="/api/recommendation", tags=["Recommendations"])
```

#### `POST /api/recommendation/get`
- **Function:** `get_recommendations(request: RecommendationRequest, shop_info)` (line 19)
- **Response Model:** `RecommendationResponse`
- **Auth:** `Depends(get_shop_authorization)`
- **Delegates to:** `recommendation_controller.get_recommendations(request, shop_info)`
- **Used by:** Venus, Atlas, Phoenix, Mercury

#### `POST /api/recommendation/get-with-session`
- **Function:** `get_recommendations_with_session(request: CombinedRecommendationRequest, shop_info)` (line 55)
- **Response Model:** `RecommendationResponse`
- **Auth:** `Depends(get_shop_authorization)`
- **Delegates to:** `recommendation_controller.get_recommendations_with_session(request, shop_info)`
- **Used by:** Apollo (primarily)

---

### 1.4 Interaction Routes

**File:** `app/routes/interaction_routes.py`

```python
router = APIRouter(prefix="/api/interaction", tags=["Interaction Tracking"])
```

#### `POST /api/interaction/track`
- **Function:** `track_interaction(request: InteractionRequest, shop_info)` (line 15)
- **Response Model:** `InteractionResponse`
- **Auth:** `Depends(get_shop_authorization)`
- **Delegates to:** `interaction_controller.track_interaction(request, shop_info)`
- **Used by:** All extensions (Venus, Atlas, Phoenix, Apollo, Mercury)

---

## 2. Request/Response Models

### 2.1 Auth Models

**File:** `app/models/auth_models.py`

```python
class GenerateTokenRequest(BaseModel):
    shop_domain: str
    customer_id: Optional[str] = None
    force_refresh: bool = False

class GenerateTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    needs_refresh: bool

class RefreshTokenRequest(BaseModel):
    refresh_token: str
    is_service_active: Optional[bool] = None
    shopify_plus: Optional[bool] = False

class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int
    refresh_expires_in: Optional[int] = None
```

### 2.2 Session Models

**File:** `app/models/session_models.py`

- `normalize_graphql_id(value)` (line 6) -- Converts `gid://shopify/Customer/123` to `123`

```python
class SessionRequest(BaseModel):  # line 27
    shop_domain: str
    customer_id: Optional[str]  # @field_validator normalizes GraphQL IDs
    browser_session_id: Optional[str]
    client_id: Optional[str]
    user_agent: Optional[str | bool]   # True = extract from headers
    ip_address: Optional[str | bool]   # True = extract from headers
    referrer: Optional[str]
    page_url: Optional[str]
    extension_type: Optional[str]

class SessionResponse(BaseModel):  # line 57
    success: bool
    message: str
    data: Optional[Dict[str, Any]]
    session_recovery: Optional[Dict[str, Any]]

class SessionAndRecommendationsRequest(BaseModel):  # line 68
    shop_domain: str
    customer_id: Optional[str]  # normalized
    browser_session_id: Optional[str]
    client_id: Optional[str]
    user_agent: Optional[str]
    ip_address: Optional[str]
    referrer: Optional[str]
    page_url: Optional[str]
    order_id: Optional[str]
    purchased_products: Optional[list]
    limit: int = Field(default=3, ge=1, le=3)
    metadata: Optional[Dict[str, Any]]
    extension_type: Optional[str]

class SessionAndRecommendationsResponse(BaseModel):  # line 111
    success: bool
    message: str
    session_data: Optional[Dict[str, Any]]
    recommendations: Optional[list]
    recommendation_count: int = 0
```

### 2.3 Interaction Models

**File:** `app/models/interaction_models.py`

```python
class InteractionRequest(BaseModel):  # line 29
    session_id: str
    shop_domain: str
    extension_type: ExtensionType  # Enum: phoenix, venus, apollo, atlas, mercury
    interaction_type: InteractionType  # Enum: recommendation_clicked, product_viewed, etc.
    customer_id: Optional[str]  # normalized GraphQL IDs
    metadata: Dict[str, Any] = {}

class InteractionResponse(BaseModel):  # line 53
    success: bool
    message: str
    interaction_id: Optional[str]
    session_recovery: Optional[Dict[str, Any]]
```

### 2.4 Recommendation Models

**File:** `app/models/recommendation_models.py`

```python
class RecommendationRequest(BaseModel):  # line 27
    shop_domain: str
    extension_type: ExtensionType
    session_id: str
    context: str  # product_page, homepage, cart, post_purchase, etc.
    user_id: Optional[str]  # normalized
    product_ids: Optional[List[str]]
    product_id: Optional[str]
    collection_id: Optional[str]
    limit: int = Field(default=6, ge=1, le=20)
    metadata: Optional[Dict[str, Any]]

class CombinedRecommendationRequest(BaseModel):  # line 59
    shop_domain: str
    extension_type: ExtensionType = ExtensionType.APOLLO
    customer_id: Optional[str]  # normalized
    browser_session_id: Optional[str]
    client_id: Optional[str]
    user_agent: Optional[str]
    ip_address: Optional[str]
    referrer: Optional[str]
    page_url: Optional[str]
    order_id: Optional[str]
    purchased_products: Optional[List[str]]
    limit: int = Field(default=3, ge=1, le=3)
    metadata: Optional[Dict[str, Any]]

class RecommendationResponse(BaseModel):  # line 97
    success: bool
    message: str
    recommendations: Optional[List[Dict[str, Any]]]
    count: int = 0
    source: Optional[str]
    session_data: Optional[Dict[str, Any]]
```

---

## 3. Controllers

### 3.1 Auth Controller

**File:** `app/controllers/auth_controller.py`

#### `generate_shop_token(request: GenerateTokenRequest)` (approx line 20)
- **SQLAlchemy Query:** `shop_repo.get_shop_info_from_domain(request.shop_domain)` which internally runs:
  ```python
  select(Shop).where(and_(Shop.shop_domain == shop_domain, Shop.is_active == True))
  select(ShopSubscription.status).where(and_(
      ShopSubscription.shop_id == shop.id,
      ShopSubscription.is_active == True
  )).order_by(ShopSubscription.created_at.desc()).limit(1)
  ```
- **Returns:** `GenerateTokenResponse(access_token, refresh_token, expires_in, needs_refresh)`
- Creates JWT token pair via `jwt_service.create_token_pair(shop_id, shop_domain, is_service_active, shopify_plus)`

#### `refresh_access_token(request: RefreshTokenRequest)` (approx line 50)
- Validates refresh token via `jwt_service.validate_refresh_token(request.refresh_token)`
- If valid and not expired: creates new access token from token payload (no DB query)
- If expired (error_code `REFRESH_TOKEN_EXPIRED`): falls back to DB lookup via `shop_repo.get_shop_by_id(shop_id)`
- **SQLAlchemy Query (DB fallback only):**
  ```python
  select(Shop).where(and_(Shop.id == shop_id, Shop.is_active == True))
  select(ShopSubscription.status).where(and_(
      ShopSubscription.shop_id == shop.id,
      ShopSubscription.is_active == True
  )).order_by(ShopSubscription.created_at.desc()).limit(1)
  ```

### 3.2 Session Controller

**File:** `app/controllers/session_controller.py`

#### `get_or_create_session(request, shop_info)` (approx line 15)
- Resolves `shop_id` from `shop_info["shop_id"]`
- Delegates to `session_service.get_or_create_session(shop_id, customer_id, browser_session_id, user_agent, ip_address, referrer, client_id)`
- Converts result to dict and returns session data

### 3.3 Interaction Controller

**File:** `app/controllers/interaction_controller.py`

#### `track_interaction(request, shop_info)` (approx line 15)
- Resolves `shop_id` from `shop_info["shop_id"]`
- Calls `interaction_service.track_interaction(session_id, extension_type, interaction_type, shop_id, customer_id, metadata)`
- **Session Recovery:** If `interaction_service` returns None (session not found), attempts to find recent session for the same customer within 30 minutes via `session_service._find_recent_customer_session(customer_id, shop_id, 30)`
- Returns `InteractionResponse(success, message, interaction_id, session_recovery)`

### 3.4 Recommendation Controller

**File:** `app/controllers/recommendation_controller.py`

#### `get_recommendations(request, shop_info)` (approx line 30)
- Requires existing session (session_id in request)
- Delegates to `recommendation_service.fetch_recommendations_logic(rec_request, services)`
- Returns `RecommendationResponse(success, message, recommendations, count, source)`

#### `get_recommendations_with_session(http_request, request, shop_info)` (line 94)
- **Combined session + recommendations for Apollo post-purchase**
- Step 1: Creates session via `session_service.get_or_create_session(shop_id, customer_id, ...)`
- Step 2: Gets post-purchase recommendations via `recommendation_service.fetch_recommendations_logic(rec_request, services)`
  - Sets `context = "post_purchase"`, `product_ids = purchased_products`
- Step 3: Tracks `recommendation_viewed` interaction via `interaction_service.track_interaction(session_id, extension_type, InteractionType.RECOMMENDATION_VIEW, ...)`
- Returns `SessionAndRecommendationsResponse(success, message, session_data, recommendations, recommendation_count)`

---

## 4. Services

### 4.1 JWT Service

**File:** `app/services/jwt_service.py`

- **Algorithm:** HS256
- **Access Token Expire:** 30 minutes (line 15)
- **Refresh Token Expire:** 90 minutes (line 16)
- **Refresh Threshold:** 15 minutes before expiry (line 17)
- **Secret Key:** `settings.SECRET_KEY`

#### Methods:
- `create_access_token(shop_id, shop_domain, is_service_active, shopify_plus) -> str` (line 19)
  - Payload: `{shop_id, shop_domain, is_service_active, shopify_plus, token_type: "access", exp, iat}`
- `create_refresh_token(shop_id, shop_domain, is_service_active, shopify_plus) -> str` (line 45)
  - Payload: `{shop_id, shop_domain, is_service_active, shopify_plus, token_type: "refresh", exp, iat}`
- `create_token_pair(...) -> Dict[str, str]` (line 71) -- Returns `{access_token, refresh_token, token_type: "Bearer", expires_in}`
- `validate_access_token(token) -> Optional[Dict]` (line 93) -- Returns `{shop_id, shop_domain, is_service_active, shopify_plus, is_valid, needs_refresh}`
- `validate_refresh_token(token) -> Optional[Dict]` (line 120) -- On expired: extracts payload without verification via `decode_token_without_verification()`, returns `{is_valid: False, error_code: "REFRESH_TOKEN_EXPIRED", shop_id, shop_domain}`
- `decode_token_without_verification(token) -> Optional[Dict]` (line 212) -- `jwt.decode(token, options={"verify_signature": False})`
- `is_token_expiring_soon(token) -> bool` (line 233)

**Known Bug (line 200-203):** `refresh_access_token()` method references `refresh_result["subscription_status"]` but the token payload uses `is_service_active` as the key name. This would cause a `KeyError` if this method is called directly (it appears to not be used -- the controller handles refresh differently).

### 4.2 Session Service

**File:** `app/services/session_service.py`

- **Anonymous Session Duration:** 30 days (line 23)
- **Identified Session Duration:** 7 days (line 24)
- **Cleanup Interval:** 1 hour (line 25)
- **Max Retries:** 3 with exponential backoff starting at 0.1s (line 403-404)

#### `get_or_create_session(shop_id, customer_id, browser_session_id, user_agent, ip_address, referrer, client_id) -> UserSession` (line 29)
1. Runs `_cleanup_expired_sessions()` (hourly)
2. Tries `_find_existing_session()` with priority:
   - Priority 1: `customer_id` -- `repository.find_active_by_customer(shop_id, customer_id, current_time)`
   - Priority 2: `client_id` -- `repository.find_active_by_client_id(shop_id, client_id, current_time)`
   - Priority 3: `browser_session_id` -- `repository.find_active_by_browser_session(shop_id, browser_session_id, current_time)`
   - Priority 4: Race condition detection -- `repository.find_recent_by_shop(shop_id, current_time)`
3. If not found, tries `_find_expired_session_for_linking()` -- extends expired session
4. If found: updates session activity in background via `asyncio.create_task()`
5. If not found: creates new session via `_create_new_session_with_retry()` with 3 retries and unique constraint handling

#### `update_session(session_id, update_data) -> Optional[UserSession]` (line 105)
- Checks for active session conflict if updating `customer_id`
- Delegates to `repository.update(session_id, **update_kwargs)`

#### `add_extension_to_session(session_id, extension_type) -> bool` (line 173)
- Adds extension type to `extensions_used` list if not already present

#### `increment_session_interactions(session_id) -> bool` (line 209)
- Delegates to `repository.increment_interactions(session_id)`

### 4.3 Interaction Service

**File:** `app/services/interaction_service.py`

#### `track_interaction(session_id, extension_type, interaction_type, shop_id, customer_id, interaction_metadata) -> Optional[UserInteraction]` (line 45)
1. Validates session exists: `session_service.get_session(session_id)`
2. Validates extension context: `_validate_extension_context(extension_type)`
3. Saves interaction to database via `_save_interaction(interaction_data)`
   - **SQLAlchemy Query:** `select(Shop).where(Shop.id == shop_id)` to validate shop
   - Creates `UserInteractionModel` with `interaction_{uuid.uuid4().hex[:16]}` ID
4. Updates session: `session_service.add_extension_to_session()`, `session_service.increment_session_interactions()`
5. If `CUSTOMER_LINKED` interaction: triggers customer linking via Kafka
6. Fires feature computation event via Kafka

**Kafka Messages Produced:**
- **Topic:** `feature-computation-jobs` via `publisher.publish_feature_computation_event()`
  - Payload: `{job_id, shop_id, features_ready: False, interaction_metadata, event_type: "feature_computation", data_type: "interactions", timestamp, source: "analytics_tracking"}`
- **Topic:** `customer-linking-jobs` via `publisher.publish_customer_linking_event()`
  - Payload: `{job_id, shop_id, customer_id, event_type: "customer_linking", trigger_session_id, linked_sessions: None, interaction_metadata: {session_id, source: "analytics_tracking_service"}}`

### 4.4 Recommendation Service

**File:** `app/services/recommendation_service.py`

Initializes a `RecommendationServices` dataclass bundling all recommendation sub-services, plus a `GorseApiClient`.

#### `fetch_recommendations_logic(request: RecommendationRequest, services: RecommendationServices) -> dict` (line 93)

**Pipeline Steps:**

1. **Resolve Shop Domain** (line 112-130)
   - If no `shop_domain` but `user_id`: `services.shop_lookup.get_shop_domain_from_customer_id(user_id)`
   - Validates shop: `services.shop_lookup.validate_shop_exists(shop_domain)`

2. **Context Handling** (line 133-169)
   - Valid contexts: `product_page`, `product_page_similar`, `product_page_frequently_bought`, `product_page_customers_viewed`, `homepage`, `cart`, `collection_page`, `profile`, `checkout_page`, `order_history`, `order_status`, `post_purchase`
   - Mercury checkout adds `mercury_checkout: True` metadata

3. **Auto-detect Category** (line 176-193)
   - For first 10 product_ids: `services.category.get_product_category(pid, shop.id)`

4. **Resolve User ID & Exclusions** (line 195-249)
   - Resolves user_id from metadata: `services.client_id_resolver.resolve_user_id_from_metadata()`
   - Resolves from session: `services.client_id_resolver.resolve_user_id_from_session_data()`
   - Gets purchase exclusions: `services.exclusion.get_smart_purchase_exclusions()`
   - Gets cart exclusions: `services.exclusion.get_cart_time_decay_exclusions()`

5. **Cache Check** (line 252-279)
   - Key generation: `services.cache.generate_cache_key(shop_id, context, product_ids, user_id, ...)`
   - On cache hit: filters by availability and exclusions, returns `{recommendations, count, source: "cache", context, timestamp}`

6. **Fetch Fresh Recommendations** (line 282-373)
   - **product_page**: `services.smart_selection.get_smart_product_page_recommendation()`
   - **homepage**: `services.smart_selection.get_smart_homepage_recommendation()`
   - **collection_page**: `services.smart_selection.get_smart_collection_page_recommendation()`
   - **cart**: `services.smart_selection.get_smart_cart_page_recommendation()`
   - **checkout_page**: FBT-only via `FrequentlyBoughtTogetherService().get_frequently_bought_together(shop_id, primary_product, limit, cart_value)`
   - **Default fallback**: `services.executor.execute_fallback_chain(context, shop_id, ...)`

7. **Enrich, Filter, Finalize** (line 385-411)
   - `services.enrichment.enrich_items(shop_id, items, context, source)`
   - Filters unavailable items and excluded items
   - Adds currency: `services.enrichment.enhance_recommendations_with_currency(items, shop_currency)`

8. **Cache & Log** (line 414-427)
   - Caches result: `services.cache.cache_recommendations(cache_key, response_data, context)`
   - Logs analytics in background: `services.analytics.log_recommendation_request(...)`

**Return:** `{recommendations, count, source, context, timestamp}`

### 4.5 Shop Cache Service

**File:** `app/services/shop_cache_service.py`

- **Cache TTL:** 300 seconds (5 minutes) (line 41)
- **Cache Namespace:** `shop_lookup` (line 42)
- **Circuit Breaker Threshold:** 5 failures (line 46)
- **Circuit Breaker Timeout:** 60 seconds (line 47)

#### `get_active_shop_by_domain(shop_domain) -> Optional[Dict]` (line 69)
1. Check circuit breaker
2. Try Redis cache: `cache_service.get("active_shop", shop_domain=shop_domain)`
3. Check negative cache: `cache_service.get("negative_shop", shop_domain=shop_domain)`
4. On cache miss: `shop_repository.get_active_by_domain(shop_domain)`
   - **SQLAlchemy Query:** `select(Shop).where((Shop.shop_domain == shop_domain) & (Shop.is_active == True))`
5. Cache result or negative result (half TTL for negatives)

**Return:** `{id, domain, is_active, plan_type, currency_code, access_token, last_analysis_at}`

---

## 5. Kafka Consumers

### 5.1 Data Collection Consumer

**File:** `app/consumers/kafka/data_collection_consumer.py`

- **Topics:** `data-collection-jobs`, `shopify-events` (line 34-35)
- **Group ID:** `data-collection-processors` (line 35)

#### `_handle_message(message)` (line 65)
- Resolves shop data via `_resolve_shop_data(payload)`
- Checks shop active status; sends to DLQ if suspended
- Routes by `event_type`:
  - `data_collection` -> `_handle_data_collection_job()`
  - `product_updated/created/deleted`, `collection_updated/created/deleted`, `order_paid/updated`, `refund_created`, `customer_created/updated`, `inventory_updated` -> `_handle_webhook_event()`

#### `_resolve_shop_data(event)` (line 137)
- For `data_collection`: `shop_repo.get_active_by_id(shop_id)`
  - **SQLAlchemy Query:** `select(Shop).where((Shop.id == shop_id) & (Shop.is_active == True))`
- For webhook events: `shop_cache.get_active_shop_by_domain(shop_domain)` (Redis-backed)

#### `_handle_webhook_event(event, shop_data)` (line 190)
- Deletion events: delegates to `normalization_service.deletion_service.handle_entity_deletion()`
- Other events: creates collection payload via `_create_collection_payload()` and processes

#### `_process_data_collection_job(job_id, shop_id, collection_payload, shop_data)` (line 293)
- **External API Call:** `shopify_service.collect_all_data(shop_domain, shop_id, access_token, collection_payload)` -- calls Shopify GraphQL Admin API

#### `_handle_deletion_event(event_type, shopify_id, shop_id)` (line 319)
- Imports `NormalizationService` and calls `normalization_service.deletion_service.handle_entity_deletion(deletion_job, None)`

**Kafka DLQ:** Sends to DLQ via `dlq_service.send_to_dlq(original_message, reason="shop_suspended", original_topic="data-collection-jobs", ...)`

---

### 5.2 Normalization Consumer

**File:** `app/consumers/kafka/normalization_consumer.py`

- **Topic:** `normalization-jobs` (line 37)
- **Group ID:** `normalization-processors` (line 37)

#### `_handle_message(message)` (line 75)
- Validates `shop_id` present
- Checks shop active: `shop_repo.is_shop_active(shop_id)`
  - **SQLAlchemy Query:** `select(Shop.is_active).where(Shop.id == shop_id)`
- Sends to DLQ if shop not active
- Routes `normalize_data` events to `_handle_unified_normalization()`

#### `_handle_unified_normalization(payload)` (line 112)
- Calls `normalization_service.normalize_data(shop_id, data_type, normalization_params)`
- On success:
  - Triggers feature computation: `normalization_service.feature_service.trigger_feature_computation(shop_id, data_type)`
  - Triggers FBT retraining for order-related data types: `_trigger_fbt_retraining_if_needed(shop_id, data_type)`

#### `_trigger_fbt_retraining_if_needed(shop_id, data_type)` (line 147)
- Only triggers for order-related types: `orders, order, order_data, line_item, line_item_data, order_paid, order_updated, order_created`
- Creates background task: `asyncio.create_task(self._retrain_fbt_model(fbt_service, shop_id, data_type))`
- Calls `fbt_service.train_fp_growth_model(shop_id)`

---

### 5.3 Feature Computation Consumer

**File:** `app/consumers/kafka/feature_computation_consumer.py`

- **Topic:** `feature-computation-jobs` (line 35)
- **Group ID:** `feature-computation-processors` (line 36)

#### `_handle_message(message)` (line 67)
- Extracts `job_id`, `shop_id`, `features_ready` from payload
- Checks shop active status; sends to DLQ if suspended
- If `features_ready` is False: calls `_compute_features_for_shop(job_id, shop_id, metadata)`

#### `_compute_features_for_shop(job_id, shop_id, metadata)` (line 131)
- `batch_size = metadata.get("batch_size", 100)`
- Calls `feature_service.run_comprehensive_pipeline_for_shop(shop_id, batch_size)`

---

### 5.4 Customer Linking Consumer

**File:** `app/consumers/kafka/customer_linking_consumer.py`

- **Topic:** `customer-linking-jobs` (line 38)
- **Group ID:** `customer-linking-processors` (line 39)

#### `_handle_message(message)` (line 70)
- Extracts `job_id`, `shop_id`, `customer_id`, `trigger_session_id`, `linked_sessions`, `event_type`
- Checks shop active; sends to DLQ if suspended
- Routes by `event_type`:
  - `customer_linking` -> `_process_customer_linking()`
  - `cross_session_linking` -> `_process_cross_session_linking()`
  - `backfill_interactions` -> `_process_interaction_backfill()`

#### `_process_customer_linking(job_id, shop_id, customer_id, trigger_session_id, linked_sessions)` (line 127)
- Calls `cross_session_linking_service.link_customer_sessions(customer_id, shop_id, trigger_session_id)`
- On success: triggers interaction backfill for all linked sessions

#### `_process_interaction_backfill(job_id, shop_id, customer_id, linked_sessions)` (line 196)
- **SQLAlchemy Query:**
  ```python
  select(UserInteraction).where(
      UserInteraction.session_id == session_id,
      UserInteraction.customer_id.is_(None)
  )
  ```
- Updates all interactions with missing `customer_id` to the resolved `customer_id`
- Fires feature computation event via `cross_session_linking_service.fire_feature_computation_event()`

---

### 5.5 Purchase Attribution Consumer

**File:** `app/consumers/kafka/purchase_attribution_consumer.py`

- **Topic:** `purchase-attribution-jobs` (line 43)
- **Group ID:** `purchase-attribution-processors` (line 44)

#### `_handle_message(message)` (line 83)
- Only processes events where `event_type == "purchase_ready_for_attribution"`
- Checks shop active; sends to DLQ if suspended

**SQLAlchemy Queries:**
```python
# Load order
select(OrderData).where(and_(
    OrderData.shop_id == shop_id,
    OrderData.order_id == str(order_id),
))

# Load line items
select(LineItemData).where(LineItemData.order_id == order.id)

# Find recent session for customer
select(UserSession).where(and_(
    UserSession.shop_id == shop_id,
    UserSession.customer_id == customer_id,
)).order_by(UserSession.created_at.desc()).limit(1)

# Find specific session from order metafields
select(UserSession).where(and_(
    UserSession.shop_id == shop_id,
    UserSession.id == session_id_from_metafields,
)).limit(1)
```

- **Session ID from Metafields:** Checks `order.metafields` list for `namespace == "bb_recommendation"` and `key == "session_id"` (line 168-181)
- **Tracking Data Detection:** `_has_tracking_data_from_extensions()` (line 345) checks:
  - Phoenix: line item properties with `_bb_rec_extension`
  - Apollo/Mercury: order metafields with `namespace == "bb_recommendation"` and `key == "extension"` or `key == "products"`
- **Interaction Check:** `_has_extension_interactions()` (line 298) -- checks for interactions in last 30 days from `phoenix`, `venus`, `apollo` extensions

**Billing Integration:**
```python
purchase_event = PurchaseEvent(order_id, customer_id, shop_id, session_id, total_amount, currency, products, ...)
billing = BillingServiceV2(session)
await billing.process_purchase_attribution(purchase_event)
```

---

### 5.6 Billing Consumer

**File:** `app/consumers/kafka/billing_consumer.py`

- **Topic:** `billing-events` (line 25)
- **Group ID:** `billing-processors` (line 25)

#### `_handle_message(message)` (line 59)
- Extracts `event_type`, `shop_id`, `plan_id` from payload
- **Note:** Handler is a stub -- contains only logging, with TODO comments for: Update shop billing status, Suspend shop services, Send billing notifications, Update access control, Trigger plan expiration workflows

---

### 5.7 Shopify Usage Consumer

**File:** `app/consumers/kafka/shopify_usage_consumer.py`

- **Topic:** `shopify-usage-events` (line 44)
- **Group ID:** `shopify-usage-processors` (line 44)

#### `_handle_message(message)` (line 80)
- Routes by `event_type`:
  - `record_usage` -> `_handle_record_usage()`
  - `cap_increase` -> `_handle_cap_increase()`
  - `reprocess_rejected_commissions` -> `_handle_reprocess_rejected()`

#### `_handle_record_usage(payload)` (line 134)
- Calls `commission_service.record_commission_to_shopify(commission_id, shopify_billing_service)`
- Uses `get_transaction_context()` for database operations

#### `_handle_cap_increase(payload)` (line 166)
- Reprocesses rejected commissions for billing cycle
- **SQLAlchemy Query (reactivate subscription):**
  ```python
  update(ShopSubscription)
      .where(ShopSubscription.id == shop_subscription.id)
      .where(ShopSubscription.status == SubscriptionStatus.SUSPENDED)
      .values(status=SubscriptionStatus.ACTIVE, updated_at=now_utc())
  ```

#### `_do_reprocess(shop_id, cycle_id, ...)` (line 288)
- **SQLAlchemy Query:**
  ```python
  select(CommissionRecord).where(and_(
      CommissionRecord.shop_id == shop_id,
      CommissionRecord.billing_cycle_id == cycle_id,
      CommissionRecord.billing_phase == "PAID",
      (CommissionRecord.status == CommissionStatus.REJECTED) |
      (CommissionRecord.status == CommissionStatus.PENDING)
  ))
  ```
- For each commission: recalculates charge amounts, updates record, records to Shopify
- Stops processing when remaining cap is exhausted (line 432-438)

---

## 6. Recommendation Engine

All recommendation engine files are in `app/recommandations/` (note: French spelling of "recommendations" in directory name).

### 6.1 Hybrid Recommendation Service

**File:** `app/recommandations/hybrid.py`

#### Blending Ratios (line 39-87)
```python
BLENDING_RATIOS = {
    "product_page": {"item_neighbors": 0.4, "user_recommendations": 0.3, "popular": 0.2, "latest": 0.1},
    "homepage": {"popular": 0.3, "user_recommendations": 0.3, "trending": 0.2, "latest": 0.2},
    "cart": {"item_neighbors": 0.4, "user_recommendations": 0.3, "popular": 0.2, "trending": 0.1},
    "profile": {"user_recommendations": 0.5, "popular": 0.2, "latest": 0.2, "trending": 0.1},
    "checkout": {"item_neighbors": 0.5, "user_recommendations": 0.3, "popular": 0.2},
    "order_history": {"user_recommendations": 0.4, "popular": 0.3, "latest": 0.2, "trending": 0.1},
    "order_status": {"item_neighbors": 0.4, "user_recommendations": 0.3, "popular": 0.2, "latest": 0.1},
    "collection_page": {"popular_category": 0.4, "popular": 0.3, "trending": 0.2, "latest": 0.1},
    "post_purchase": {"item_neighbors": 0.5, "user_recommendations": 0.3, "popular": 0.2},
}
```

#### `blend_recommendations(shop_id, context, product_ids, user_id, session_id, category, limit, metadata, exclude_items) -> Dict` (line 89)
- Collects from multiple sources based on context ratios
- Deduplicates by item ID
- Applies cross-context deduplication
- Multi-tenancy: prefixes IDs with `shop_{shop_id}_{id}` (Gorse format)

#### `_get_source_recommendations(source_type, shop_id, ...)` (line 269)
- **Gorse REST API calls:**
  - `item_neighbors`: `gorse_client.get_item_neighbors(prefixed_item_id, n=limit)`
  - `user_recommendations`: `gorse_client.get_recommendations(prefixed_user_id, n=limit, category=category)`
  - `session_recommendations`: `gorse_client.get_session_recommendations(session_data, n=limit)`
  - `popular`: `gorse_client.get_popular_items(n=limit, category=category)`
  - `latest`: `gorse_client.get_latest_items(n=limit, category=category)`
  - `trending`: `gorse_client.get_popular_items(n=limit)` (same as popular)
  - `popular_category`: `gorse_client.get_popular_items(n=limit, category=category)`
  - `user_neighbors`: `gorse_client.get_user_neighbors(prefixed_user_id, n=10)`

### 6.2 FP-Growth Engine

**File:** `app/recommandations/fp_growth_engine.py`

#### Configuration (FPGrowthConfig dataclass):
```python
min_support = 0.01
min_confidence = 0.30
min_lift = 1.5
max_rules = 10000
days_back = 90
min_transactions = 50
```

#### `train_model(shop_id) -> Dict` (line 108)
- Loads transactions via `_load_transactions()`
- **SQLAlchemy Query (line 512):**
  ```python
  select(OrderData.id, LineItemData.product_id, OrderData.order_date)
      .join(LineItemData)
      .where(and_(
          OrderData.shop_id == shop_id,
          OrderData.order_date >= cutoff_date,
          func.lower(OrderData.financial_status) == "paid",
          LineItemData.product_id.isnot(None)
      ))
  ```
- Trains FP-Growth model using `mlxtend` library with fallback
- Caches rules to Redis

#### `_cache_rules(shop_id, rules)` (line 611)
- **Redis Key:** `fp_growth_rules:{shop_id}`
- **TTL:** 86400 seconds (24 hours)

#### `get_recommendations(shop_id, product_id, limit, cart_items) -> Dict` (line 419)
- Gets FBT recommendations with business rules filtering and semantic boosting
- Returns `{success, items, source, rule_count, confidence_stats}`

### 6.3 Product Embeddings

**File:** `app/recommandations/product_embeddings.py`

#### Configuration (EmbeddingConfig):
```python
vector_size = 200
window = 3
min_count = 5
epochs = 25
sg = 1  # Skip-gram
```

#### `train_embeddings(shop_id) -> Dict` (line 73)
- Trains Word2Vec on purchase sequences using gensim
- Fallback to co-occurrence matrix if Word2Vec fails
- **Redis Cache Key:** `product_embeddings:{shop_id}`, **TTL:** 86400 seconds

#### `boost_recommendations(recommendations, shop_id, product_id) -> List` (line 186)
- Cosine similarity tiers: `>0.8: 1.3x`, `>0.6: 1.2x`, `>0.4: 1.1x`

#### `_load_purchase_sequences(shop_id) -> List[List[str]]` (line 269)
- **SQLAlchemy Query:**
  ```python
  select(OrderData.customer_id, LineItemData.product_id, OrderData.order_date)
      .join(LineItemData)
      .where(and_(
          OrderData.shop_id == shop_id,
          OrderData.order_date >= cutoff_date,
          func.lower(OrderData.financial_status) == "paid"
      ))
  ```

### 6.4 Smart Selection Service

**File:** `app/recommandations/smart_selection_service.py`

Intelligently selects the best recommendation type based on data availability by testing each type with `limit=1`.

#### Methods:
- `get_smart_product_page_recommendation(shop_id, product_ids, user_id, limit)` -- Tests: item_neighbors, FBT, user_recommendations, popular
- `get_smart_homepage_recommendation(shop_id, user_id, limit)` -- Tests: user_recommendations, popular, latest, trending
- `get_smart_cart_page_recommendation(shop_id, cart_items, user_id, limit)` -- Tests: item_neighbors (first cart item), FBT, user_recommendations, popular
- `get_smart_checkout_recommendation(shop_id, user_id, limit)` -- Tests: user_recommendations, popular
- `get_smart_collection_page_recommendation(shop_id, collection_id, category, user_id, limit)` -- Tests: popular_category, popular, trending

### 6.5 Exclusion Service

**File:** `app/recommandations/exclusion_service.py`

#### `get_purchase_exclusions(session, shop_id, user_id, context) -> List[str]` (line 25)
- Context-specific exclusion strategies:
  - `order_history`, `order_status`: 30 days
  - `product_page`, `homepage`, `profile`: all-time
  - `cart`: 14 days
  - `post_purchase`: none (no exclusions)

#### `apply_time_decay_filtering(interactions, current_time) -> List[str]` (line 210)
- Only excludes items added to cart in last ~36 seconds

#### `get_cart_time_decay_exclusions(session, shop_id, user_id) -> List[str]` (line 331)
- **SQLAlchemy Query:**
  ```python
  select(UserInteraction).where(and_(
      UserInteraction.shop_id == shop_id,
      UserInteraction.customer_id == user_id,
      UserInteraction.interaction_type.in_(["product_added_to_cart", "product_removed_from_cart"]),
      UserInteraction.created_at >= (now - 48h)
  ))
  ```

### 6.6 Enrichment Service

**File:** `app/recommandations/enrichment.py`

#### `enrich_items(shop_id, items, context, source) -> List[Dict]` (line 111)
- Strips `shop_{shop_id}_` prefix from Gorse item IDs
- Validates numeric product IDs
- **SQLAlchemy Queries:**
  ```python
  select(Shop).where(Shop.id == shop_id)
  select(ProductData).where(and_(
      ProductData.shop_id == shop_id,
      ProductData.product_id.in_(clean_item_ids)
  ))
  ```
- Checks per-variant inventory for availability (None = unlimited, >0 = in stock)
- Returns enriched product objects with title, handle, price, images, variants, availability

### 6.7 Frequently Bought Together Service

**File:** `app/recommandations/frequently_bought_together.py`

#### `get_frequently_bought_together(shop_id, product_id, limit, cart_value) -> Dict` (line 75)
- Three-layer system:
  1. FP-Growth engine with semantic boosting
  2. Legacy co-occurrence fallback
  3. Popular items fallback

**Legacy SQLAlchemy Query:**
```python
select(OrderData.id)
    .join(LineItemData)
    .where(and_(
        OrderData.shop_id == shop_id,
        LineItemData.product_id == product_id,
        OrderData.financial_status == "paid"
    ))
```

### 6.8 Recommendation Executor

**File:** `app/recommandations/recommendation_executor.py`

#### `execute_recommendation_level(level_type, shop_id, ...) -> Dict` (line 40)
- Routes to recommendation types:
  - `item_neighbors`: Gorse `get_item_neighbors()`
  - `user_recommendations`: Gorse `get_recommendations()`
  - `session_recommendations`: Gorse `get_session_recommendations()`
  - `popular`: Gorse `get_popular_items()`
  - `latest`: Gorse `get_latest_items()`
  - `trending`: Gorse `get_popular_items()`
  - `popular_category`: Gorse `get_popular_items(category=category)`
  - `user_neighbors`: Custom collaborative filtering
  - `frequently_bought_together`: FP-Growth engine
  - `recently_viewed`: UserInteraction query

#### `execute_fallback_chain(context, ...) -> Dict` (line 433)
- Executes fallback levels per context

#### `_get_default_fallback_levels(context) -> List[str]` (line 508)
- Default fallback chains for 8+ contexts

### 6.9 Recommendation Cache

**File:** `app/recommandations/cache.py`

- **All CACHE_TTL values set to 0** (caching disabled)
- **Cache Key Prefix:** `rec:`
- Key generation: MD5 hash of parameters

### 6.10 Business Rules Filter

**File:** `app/recommandations/business_rules_filter.py`

Five-step filtering pipeline:
1. **Price Filter:** Filters recommendations within price range relative to source product
2. **Category Affinity:** Pre-computed category affinity matrix (line 651-771)
3. **Inventory Filter:** Checks product availability
4. **Margin Optimization:** Boosts higher-margin products
5. **Temporal Patterns:** Seasonal boost based on product categories

### 6.11 Category Detection

**File:** `app/recommandations/category_detection.py`

- **Redis Key:** `product_category:{shop_id}:{product_id}`, **TTL:** 3600 (1h)
- **SQLAlchemy Query:** `select(ProductData).where(ProductData.shop_id == shop_id, ProductData.product_id == product_id)`

### 6.12 Client ID Resolver

**File:** `app/recommandations/client_id_resolver.py`

- Resolves user_id from client_id, session_id, or metadata
- **SQLAlchemy Queries:**
  ```python
  select(UserIdentityLink.customer_id).where(and_(
      UserIdentityLink.shop_id == shop_id,
      UserIdentityLink.identifier == client_id,
      UserIdentityLink.identifier_type == "client_id"
  ))

  select(UserSession.client_id, UserSession.customer_id).where(
      UserSession.id == session_id
  )
  ```

### 6.13 Purchase History Service

**File:** `app/recommandations/purchase_history.py`

#### `get_purchased_product_ids(session, shop_id, user_id, days_back) -> List[str]` (line 22)
- **SQLAlchemy Query:**
  ```python
  select(OrderData).where(and_(
      OrderData.shop_id == shop_id,
      OrderData.customer_id == user_id,
      OrderData.order_date >= cutoff_date
  )).order_by(OrderData.order_date.desc())
  ```

#### `should_exclude_product(product_type, days_since_purchase) -> bool` (line 138)
- Repurchasable types (consumable, food, beauty): exclude for 60 days
- Durable goods: exclude all-time

### 6.14 Recently Viewed Service

**File:** `app/recommandations/recently_viewed.py`

- **SQLAlchemy Query:**
  ```python
  select(UserInteraction.interaction_metadata, UserInteraction.created_at)
      .where(and_(
          UserInteraction.shop_id == shop_id,
          UserInteraction.customer_id == user_id,
          UserInteraction.interaction_type == "product_viewed",
          UserInteraction.interaction_metadata["productId"].astext.isnot(None),
          UserInteraction.created_at >= cutoff
      ))
  ```

### 6.15 Session Data Service

**File:** `app/recommandations/session_service.py`

Extracts cart and browsing data from behavioral events.

**Three SQLAlchemy queries from UserInteraction table (last 24h):**
- Cart events: `interaction_type.in_(["product_added_to_cart", "product_removed_from_cart"])`
- View events: `interaction_type == "product_viewed"`
- Add events: `interaction_type == "product_added_to_cart"`

### 6.16 User Neighbors Service

**File:** `app/recommandations/user_neighbors.py`

Collaborative filtering via Gorse user neighbors.

- **Gorse API:** `get_user_neighbors(prefixed_user_id, n=10)`
- **SQLAlchemy Query:**
  ```python
  select(OrderData).where(and_(
      OrderData.shop_id == shop_id,
      OrderData.customer_id.in_(neighbor_ids),
      OrderData.created_at >= (now - 90d)
  ))
  ```

### 6.17 Shop Lookup Service

**File:** `app/recommandations/shop_lookup_service.py`

- **SQLAlchemy Queries:**
  ```python
  select(CustomerData).where(CustomerData.customer_id == customer_id)
  select(Shop).where(Shop.id == shop_id)
  ```

### 6.18 Recommendation Analytics

**File:** `app/recommandations/analytics.py`

- **Redis List:** `analytics:recommendations:{date}`, **TTL:** 30 days
- Logs recommendation request metadata

---

## 7. Repositories

### 7.1 ShopRepository

**File:** `app/repository/ShopRepository.py`

#### `get_active_by_id(shop_id) -> Optional[Shop]` (line 18)
```python
select(Shop).where((Shop.id == shop_id) & (Shop.is_active == True))
```

#### `get_active_by_domain(shop_domain) -> Optional[Shop]` (line 41)
```python
select(Shop).where((Shop.shop_domain == shop_domain) & (Shop.is_active == True))
```

#### `is_shop_active(shop_id) -> bool` (line 64)
```python
select(Shop.is_active).where(Shop.id == shop_id)
```

#### `get_shop_by_id(shop_id) -> Dict` (line 73)
```python
select(Shop).where(and_(Shop.id == shop_id, Shop.is_active == True))
select(ShopSubscription.status).where(and_(
    ShopSubscription.shop_id == shop.id,
    ShopSubscription.is_active == True
)).order_by(ShopSubscription.created_at.desc()).limit(1)
```
- Returns: `{shop_id, shop_domain, is_service_active, shopify_plus}`
- `is_service_active = True` only when subscription status is `ACTIVE` or `TRIAL`

#### `get_shop_info_from_domain(shop_domain) -> Dict` (line 121)
- Same queries as `get_shop_by_id` but uses `Shop.shop_domain == shop_domain`
- Returns: `{shop_id, shop_domain, is_service_active, shopify_plus}`

### 7.2 ProductRepository

**File:** `app/repository/ProductRepository.py`

#### `get_by_id(shop_id, product_id) -> Optional[ProductData]`
```python
select(ProductData).where(and_(
    ProductData.shop_id == shop_id,
    ProductData.product_id == product_id
))
```

### 7.3 OrderRepository

**File:** `app/repository/OrderRepository.py`

#### `get_by_product_id(shop_id, product_id) -> List[OrderData]`
```python
select(OrderData).join(LineItemData).where(and_(
    OrderData.shop_id == shop_id,
    LineItemData.product_id == product_id
)).options(selectinload(OrderData.line_items))
```

### 7.4 CustomerRepository

**File:** `app/repository/CustomerRepository.py`

#### `get_shop_domain_from_id(customer_id) -> Optional[str]`
```python
select(CustomerData).where(
    CustomerData.customer_id == customer_id
).options(joinedload(CustomerData.shop))
```

### 7.5 UserSessionRepository

**File:** `app/repository/UserSessionRepository.py`

Extensive session management with the following methods:

- `create(session_id, shop_id, customer_id, browser_session_id, client_id, user_agent, ip_address, referrer, created_at, expires_at)`
- `get_by_id(session_id)`
- `get_active_by_id(session_id, current_time)` -- checks status and expiry
- `update(session_id, **kwargs)`
- `find_active_by_customer(shop_id, customer_id, current_time)` -- priority 1 lookup
- `find_active_by_client_id(shop_id, client_id, current_time)` -- priority 2 lookup
- `find_active_by_browser_session(shop_id, browser_session_id, current_time)` -- priority 3 lookup
- `find_recent_by_shop(shop_id, current_time)` -- race condition detection
- `find_expired_for_linking(shop_id, customer_id, client_id, current_time)` -- finds recently expired sessions
- `check_active_session_conflict(shop_id, customer_id, exclude_session_id, current_time)`
- `terminate(session_id)`
- `mark_expired_sessions(current_time)`
- `delete_old_sessions(cutoff_date)`
- `increment_interactions(session_id)`
- `update_last_active(session_id, current_time)`
- `validate_shop_exists_and_active(shop_id)`
- `find_recent_customer_session(customer_id, shop_id, current_time, minutes_back)`

### 7.6 UserInteractionRepository

**File:** `app/repository/UserInteractionRepository.py`

#### `get_by_product_id(shop_id, product_id)`
```python
select(UserInteraction).where(and_(
    UserInteraction.shop_id == shop_id,
    UserInteraction.interaction_metadata["productId"].astext == product_id
))
```

### 7.7 CollectionRepository

**File:** `app/repository/CollectionRepository.py`

#### `get_by_product_id(shop_id, product_id)`
- JSONB containment query:
```python
select(CollectionData).where(and_(
    CollectionData.shop_id == shop_id,
    CollectionData.products.cast(JSONB).contains([{"id": product_id}])
))
```

### 7.8 RawDataRepository

**File:** `app/repository/RawDataRepository.py`

- `get_raw_count(shop_id, model_class)` -- for RawProduct, RawOrder, RawCustomer, RawCollection
- `get_latest_shopify_timestamp(shop_id, model_class)` -- returns most recent `shopify_updated_at`

### 7.9 PurchaseAttributionRepository

**File:** `app/repository/PurchaseAttributionRepository.py`

- CRUD operations for PurchaseAttribution
- `get_total_revenue_by_shop(shop_id)`:
```python
select(func.sum(PurchaseAttribution.total_revenue)).where(
    PurchaseAttribution.shop_id == shop_id
)
```

### 7.10 CommissionRepository

**File:** `app/repository/CommissionRepository.py`

- CRUD operations for CommissionRecord
- `get_by_purchase_attribution_id(purchase_attribution_id)`
- `get_by_shop(shop_id)`

### 7.11 BillingCycleRepository

**File:** `app/repository/BillingCycleRepository.py`

#### `get_current_by_subscription(shop_subscription_id)`
```python
select(BillingCycle).where(and_(
    BillingCycle.shop_subscription_id == shop_subscription_id,
    BillingCycle.status == BillingCycleStatus.ACTIVE
))
```

### 7.12 BillingInvoiceRepository

**File:** `app/repository/BillingInvoiceRepository.py`

- `create_from_webhook(shopify_invoice_data)`
- `update_from_webhook(shopify_invoice_id, update_data)`
- `_determine_status(shopify_status) -> InvoiceStatus`

### 7.13 SubscriptionTrialRepository

**File:** `app/repository/SubscriptionTrialRepository.py`

#### `check_completion(trial_id)`
- Atomic trial completion:
```python
update(SubscriptionTrial)
    .where(and_(
        SubscriptionTrial.id == trial_id,
        SubscriptionTrial.status == TrialStatus.ACTIVE
    ))
    .values(status=TrialStatus.COMPLETED)
```

---

## 8. Core Infrastructure

### 8.1 Database Engine

**File:** `app/core/database/engine.py`

- **Pool:** NullPool (for async compatibility)
- **Singleton pattern** with health monitoring every 5 minutes
- **Connection retry:** 3 attempts with exponential backoff
- **Circuit breaker:** Opens after 5 consecutive failures
- **PostgreSQL connect_args:** `command_timeout`, `tcp_keepalives` enabled

### 8.2 Database Session

**File:** `app/core/database/session.py`

#### `get_session_context()` -- Context manager
- Auto-rollback on error
- Read-only session (no auto-commit)

#### `get_transaction_context()` -- Context manager
- Auto-commit on success
- Auto-rollback on error

#### `with_database_retry(func, max_retries, timeout)` -- Retry logic
- Exponential backoff
- Detects retryable errors (connection refused, timeout, pool exhausted)

#### `database_retry` decorator
- Wraps functions with retry logic

### 8.3 Kafka Consumer

**File:** `app/core/kafka/consumer.py`

- Uses `aiokafka` library
- Static group membership for faster rebalancing
- Error handling for coordination errors, heartbeat failures, rebalancing
- Health status tracking with consecutive error counter

### 8.4 Kafka Producer

**File:** `app/core/kafka/producer.py`

- `ShopBasedPartitioning` strategy -- consistent partitioning by shop_id
- `send(topic, value, key)` adds metadata: `{timestamp, message_id, worker_id}`
- Optional explicit partitioning with fallback

### 8.5 Consumer Manager

**File:** `app/core/kafka/consumer_manager.py`

Manages 7 consumers:
1. `data_collection` -- DataCollectionKafkaConsumer
2. `normalization` -- NormalizationKafkaConsumer
3. `feature_computation` -- FeatureComputationKafkaConsumer
4. `purchase_attribution` -- PurchaseAttributionKafkaConsumer
5. `customer_linking` -- CustomerLinkingKafkaConsumer
6. `billing` -- BillingKafkaConsumer
7. `shopify_usage` -- ShopifyUsageKafkaConsumer

**Circuit Breaker:** threshold=10 failures, exponential backoff 5s-60s

Global instance: `consumer_manager = KafkaConsumerManager()`

### 8.6 Event Publisher

**File:** `app/core/messaging/event_publisher.py`

Published topics:
- `shopify-events`
- `data-collection-jobs`
- `ml-training`
- `billing-events`
- `shopify-usage-events`
- `access-control`
- `normalization-jobs`
- `behavioral-events`
- `analytics-events`
- `notification-events`
- `integration-events`
- `audit-events`
- `feature-computation-jobs`
- `customer-linking-jobs`
- `purchase-attribution-jobs`

### 8.7 Redis Client

**File:** `app/core/redis_client.py`

- Singleton Redis client
- TLS support
- `socket_connect_timeout=10s`
- `socket_timeout=5s`
- `health_check_interval=30s`

### 8.8 Settings

**File:** `app/core/config/settings.py`

- `DatabaseSettings`: pool config, query timeout
- `RedisSettings`: URL, TLS
- `ShopifySettings`: API version, webhooks
- `MLSettings`: Gorse URL/API key
- `WorkerSettings`: concurrency, batch size
- `LoggingSettings`: level, format

Key defaults:
- `MAX_RETRIES = 5`
- `RETRY_DELAY = 2.0`
- `DATABASE_QUERY_TIMEOUT = 30`
- `DATABASE_HEALTH_CHECK_INTERVAL = 300`

### 8.9 Kafka Settings

**File:** `app/core/config/kafka_settings.py`

Topic configurations:
| Topic | Partitions | Replication | Retention |
|-------|-----------|-------------|-----------|
| shopify-events | 6 | - | - |
| data-collection-jobs | 4 | - | - |
| normalization-jobs | 4 | - | - |
| billing-events | 4 | - | - |
| shopify-usage-events | 4 | - | - |
| feature-computation-jobs | 2 | - | - |
| customer-linking-jobs | 4 | - | - |
| purchase-attribution-jobs | 6 | - | - |

Consumer config:
- `session_timeout = 30s`
- `heartbeat_interval = 10s`
- `max_poll_interval = 5 minutes`

---

## 9. Database Models

### 9.1 Base Classes

**File:** `app/core/database/models/base.py`

```python
Base = declarative_base()

class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=...)

class IDMixin:
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

class BaseModel(Base, IDMixin, TimestampMixin):
    __abstract__ = True
    # to_dict(), update_from_dict(), get_table_name()

class ShopMixin:
    shop_id = Column(String, ForeignKey("shops.id"), nullable=False, index=True)

class CustomerMixin:
    customer_id = Column(String, nullable=True, index=True)

class ProductMixin:
    product_id = Column(String, nullable=True, index=True)

class OrderMixin:
    order_id = Column(String, nullable=True, index=True)

class SessionMixin:
    session_id = Column(String, nullable=True, index=True)
```

### 9.2 Enums

**File:** `app/core/database/models/enums.py`

```python
class RawSourceType: WEBHOOK, BACKFILL
class RawDataFormat: REST, GRAPHQL
class BillingPlanType: REVENUE_SHARE, PERFORMANCE_TIER, HYBRID, USAGE_BASED
class BillingPlanStatus: ACTIVE, INACTIVE, SUSPENDED, TRIAL
class BillingCycle: MONTHLY, QUARTERLY, ANNUALLY
class InvoiceStatus: DRAFT, PENDING, PAID, OVERDUE, CANCELLED, REFUNDED, FAILED
class ExtensionType: APOLLO, ATLAS, PHOENIX, VENUS, MERCURY
class AppBlockTarget: CUSTOMER_ACCOUNT_ORDER_STATUS_BLOCK_RENDER, CUSTOMER_ACCOUNT_ORDER_INDEX_BLOCK_RENDER, CUSTOMER_ACCOUNT_PROFILE_BLOCK_RENDER, CHECKOUT_POST_PURCHASE, THEME_APP_EXTENSION, WEB_PIXEL_EXTENSION
class BillingPhase: TRIAL, PAID
class CommissionStatus: TRIAL_PENDING, TRIAL_COMPLETED, PENDING, RECORDED, INVOICED, REJECTED, FAILED, CAPPED
class ChargeType: FULL, PARTIAL, OVERFLOW_ONLY, TRIAL, REJECTED
class SubscriptionPlanType: USAGE_BASED, TIERED, FLAT_RATE, HYBRID
class SubscriptionType: TRIAL, PAID
class SubscriptionStatus: ACTIVE, COMPLETED, CANCELLED, SUSPENDED, EXPIRED, TRIAL, TRIAL_COMPLETED, PENDING_APPROVAL
class BillingCycleStatus: ACTIVE, COMPLETED, CANCELLED, SUSPENDED
class TrialStatus: ACTIVE, COMPLETED, EXPIRED, CANCELLED
class ShopifySubscriptionStatus: PENDING, ACTIVE, DECLINED, CANCELLED, EXPIRED
class AdjustmentReason: CAP_INCREASE, PLAN_UPGRADE, ADMIN_ADJUSTMENT, PROMOTION, DISPUTE_RESOLUTION
```

### 9.3 Shop

**File:** `app/core/database/models/shop.py` -- Table: `shops`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_domain | String(255) | Unique, indexed |
| custom_domain | String(255) | nullable |
| access_token | String(1000) | not null |
| plan_type | String(50) | default "Free" |
| currency_code | String(10) | nullable |
| money_format | String(100) | nullable |
| is_active | Boolean | default True |
| onboarding_completed | Boolean | default False |
| shopify_plus | Boolean | default False |
| suspended_at | TIMESTAMP | nullable |
| suspension_reason | String(255) | nullable |
| service_impact | String(50) | nullable: 'suspended', 'active', 'limited' |
| email | String(255) | nullable |
| last_analysis_at | TIMESTAMP | nullable |

**Relationships:** collection_data, collection_features, customer_behavior_features, customer_data, interaction_features, order_data, product_data, product_features, product_pair_features, search_product_features, session_features, user_features, purchase_attributions, user_interactions, user_sessions, shop_subscriptions, commission_records

### 9.4 Session (Shopify App Session)

**File:** `app/core/database/models/session.py` -- Table: `sessions`

| Column | DB Name | Type | Notes |
|--------|---------|------|-------|
| id | id | String | PK |
| shop | shop | String | not null |
| state | state | String | not null |
| is_online | isOnline | Boolean | not null |
| scope | scope | String(500) | nullable |
| expires | expires | TIMESTAMP | nullable |
| access_token | accessToken | String(1000) | not null |
| user_id | userId | BigInteger | nullable |
| first_name | firstName | String(100) | nullable |
| last_name | lastName | String(100) | nullable |
| email | email | String(255) | nullable |
| account_owner | accountOwner | Boolean | not null |
| locale | locale | String(10) | nullable |
| collaborator | collaborator | Boolean | nullable |
| email_verified | emailVerified | Boolean | nullable |

**Note:** Uses camelCase column names for Remix/Prisma compatibility.

### 9.5 UserSession

**File:** `app/core/database/models/user_session.py` -- Table: `user_sessions`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| customer_id | String | nullable, indexed |
| browser_session_id | String(255) | nullable |
| status | String(50) | default "active" |
| client_id | String | nullable, indexed |
| last_active | TIMESTAMP | not null |
| expires_at | TIMESTAMP | nullable |
| user_agent | String | nullable |
| ip_address | String(45) | nullable |
| referrer | String | nullable |
| extensions_used | JSON | default [] |
| total_interactions | Integer | default 0 |

**Partial Indexes:**
- `ix_active_by_customer`: `(shop_id, customer_id, status, expires_at)` WHERE `customer_id IS NOT NULL AND status = 'active'`
- `ix_active_by_client_id`: `(shop_id, client_id, status, expires_at)` WHERE `client_id IS NOT NULL AND status = 'active'`
- `ix_active_by_browser_session`: `(shop_id, browser_session_id, status, expires_at)` WHERE `browser_session_id IS NOT NULL AND status = 'active'`

### 9.6 UserInteraction

**File:** `app/core/database/models/user_interaction.py` -- Table: `user_interactions`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| customer_id | String | nullable |
| session_id | String(255) | FK -> user_sessions.id |
| extension_type | String(50) | not null |
| interaction_type | String(50) | not null |
| interaction_metadata | JSON | default {} |

### 9.7 OrderData

**File:** `app/core/database/models/order_data.py` -- Table: `order_data`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| order_id | String | not null, indexed |
| order_name | String(100) | nullable |
| customer_id | String(100) | nullable, indexed |
| total_amount | Float | default 0.0 |
| subtotal_amount | Float | nullable |
| order_date | TIMESTAMP | not null, indexed |
| financial_status | String(50) | nullable, indexed |
| fulfillment_status | String(50) | nullable, indexed |
| tags | JSON | default [] |
| metafields | JSON | default [] |
| line_items | relationship | -> LineItemData |

### 9.8 LineItemData

**File:** `app/core/database/models/order_data.py` -- Table: `line_item_data`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| order_id | String | FK -> order_data.id |
| product_id | String | nullable |
| variant_id | String | nullable |
| title | String | nullable |
| quantity | Integer | not null |
| price | Float | not null |
| original_unit_price | Float | nullable |
| discounted_unit_price | Float | nullable |
| currency_code | String(10) | nullable |
| variant_data | JSON | default {} |
| properties | JSON | default {} |

### 9.9 ProductData

**File:** `app/core/database/models/product_data.py` -- Table: `product_data`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| product_id | String | not null, indexed |
| title | String(500) | not null |
| handle | String(255) | not null |
| description | Text | nullable |
| product_type | String(100) | nullable, indexed |
| vendor | String(255) | nullable |
| tags | JSON | default [] |
| status | String | default "ACTIVE", indexed |
| total_inventory | Integer | nullable, indexed |
| price | Float | default 0.0, indexed |
| compare_at_price | Float | nullable |
| price_range | JSON | default {} |
| collections | JSON | default [] |
| variants | JSON | default [] |
| images | JSON | default [] |
| media | JSON | default [] |
| options | JSON | default [] |
| metafields | JSON | default [] |
| is_active | Boolean | default True, indexed |

### 9.10 CustomerData

**File:** `app/core/database/models/customer_data.py` -- Table: `customer_data`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| customer_id | String | not null, indexed |
| first_name | String(100) | nullable |
| last_name | String(100) | nullable |
| total_spent | Float | default 0.0, indexed |
| order_count | Integer | default 0 |
| last_order_date | TIMESTAMP | nullable, indexed |
| verified_email | Boolean | default False |
| state | String(50) | nullable, indexed |
| default_address | JSON | default {} |
| is_active | Boolean | default True |

### 9.11 CollectionData

**File:** `app/core/database/models/collection_data.py` -- Table: `collection_data`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| collection_id | String | not null, indexed |
| title | String(500) | not null, indexed |
| handle | String(255) | not null, indexed |
| description | Text | nullable |
| product_count | Integer | default 0, indexed |
| is_automated | Boolean | default False, indexed |
| products | JSON | default [] |

### 9.12 Raw Data Models

**File:** `app/core/database/models/raw_data.py`

Four raw data tables with identical structure:
- `raw_orders` -- RawOrder
- `raw_products` -- RawProduct
- `raw_customers` -- RawCustomer
- `raw_collections` -- RawCollection

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| payload | JSON | not null |
| extracted_at | TIMESTAMP | not null |
| shopify_id | String(100) | nullable |
| shopify_created_at | TIMESTAMP | nullable |
| shopify_updated_at | TIMESTAMP | nullable |
| source | String | default "webhook", indexed |
| format | String | default "rest", indexed |
| received_at | TIMESTAMP | nullable |

**Indexes per table:** `(shop_id, shopify_id)`, `(shop_id, shopify_updated_at)`, `(shop_id, shopify_created_at)`, `(shop_id, source)`, `(shop_id, format)`

### 9.13 UserIdentityLink

**File:** `app/core/database/models/identity.py` -- Table: `user_identity_links`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| identifier | String | not null, indexed |
| identifier_type | String | not null, indexed |
| customer_id | String | not null, indexed |
| linked_at | TIMESTAMP | not null |

**Unique Index:** `(shop_id, identifier, customer_id)`

### 9.14 PurchaseAttribution

**File:** `app/core/database/models/purchase_attribution.py` -- Table: `purchase_attributions`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| customer_id | String | nullable |
| session_id | String(255) | FK -> user_sessions.id |
| order_id | String(255) | not null, indexed |
| contributing_extensions | JSON | not null |
| attribution_weights | JSON | not null |
| total_revenue | DECIMAL(10,2) | not null |
| attributed_revenue | JSON | not null |
| total_interactions | Integer | not null |
| interactions_by_extension | JSON | not null |
| purchase_at | TIMESTAMP | not null, indexed |
| attribution_algorithm | String(50) | default "multi_touch" |
| attribution_metadata | JSON | default {} |

**Unique Index:** `(shop_id, order_id)`

### 9.15 Feature Models

**File:** `app/core/database/models/features.py`

Eight feature tables:

#### UserFeatures (Table: `user_features`)
- Unique: `(shop_id, customer_id)`
- Fields: total_purchases, total_interactions, lifetime_value, avg_order_value, purchase_frequency_score, interaction_diversity_score, days_since_last_purchase, recency_score, conversion_rate, primary_category, category_diversity, user_lifecycle_stage, churn_risk_score

#### ProductFeatures (Table: `product_features`)
- Unique: `(shop_id, product_id)`
- Fields: interaction_volume_score, purchase_velocity_score, engagement_quality_score, price_tier, revenue_potential_score, conversion_efficiency, days_since_last_purchase, activity_recency_score, trending_momentum, product_lifecycle_stage, inventory_health_score, product_category

#### CollectionFeatures (Table: `collection_features`)
- Unique: `(shop_id, collection_id)`
- Fields: collection_engagement_score, collection_conversion_rate, collection_popularity_score, avg_product_value, collection_revenue_potential, product_diversity_score, collection_size_tier, days_since_last_interaction, collection_recency_score, is_curated_collection

#### InteractionFeatures (Table: `interaction_features`)
- Unique: `(shop_id, customer_id, product_id)`
- Fields: interaction_strength_score, customer_product_affinity, engagement_progression_score, conversion_likelihood, purchase_intent_score, interaction_recency_score, relationship_maturity, interaction_frequency_score, customer_product_loyalty, total_interaction_value

#### SessionFeatures (Table: `session_features`)
- Unique: `(shop_id, session_id)`
- Fields: session_duration_minutes, interaction_count, interaction_intensity, unique_products_viewed, browse_depth_score, conversion_funnel_stage, purchase_intent_score, session_value, session_type, bounce_session, traffic_source, returning_visitor

#### ProductPairFeatures (Table: `product_pair_features`)
- Unique: `(shop_id, product_id1, product_id2)`
- Fields: co_purchase_strength, co_engagement_score, pair_affinity_score, total_pair_revenue, pair_frequency_score, days_since_last_co_occurrence, pair_recency_score, pair_confidence_level, cross_sell_potential

#### SearchProductFeatures (Table: `search_product_features`)
- Unique: `(shop_id, search_query, product_id)`
- Fields: search_click_rate, search_conversion_rate, search_relevance_score, total_search_interactions, search_to_purchase_count, days_since_last_search_interaction, search_recency_score, semantic_match_score, search_intent_alignment

#### CustomerBehaviorFeatures (Table: `customer_behavior_features`)
- Unique: `(shop_id, customer_id)`
- Fields: user_lifecycle_stage, purchase_frequency_score, interaction_diversity_score, category_diversity, primary_category, conversion_rate, avg_order_value, lifetime_value, recency_score, churn_risk_score, total_interactions, days_since_last_purchase

### 9.16 Billing Models

#### SubscriptionPlan (Table: `subscription_plans`)

**File:** `app/core/database/models/subscription_plan.py`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| name | String(100) | unique, indexed |
| description | Text | nullable |
| plan_type | SubscriptionPlanType enum | not null |
| is_active | Boolean | default True |
| is_default | Boolean | default False |
| default_commission_rate | String(10) | nullable |
| plan_metadata | Text | nullable (JSON string) |
| effective_from | TIMESTAMP | not null |
| effective_to | TIMESTAMP | nullable |

#### PricingTier (Table: `pricing_tiers`)

**File:** `app/core/database/models/pricing_tier.py`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| subscription_plan_id | String(255) | FK -> subscription_plans.id |
| currency | String(3) | not null (ISO 4217) |
| trial_threshold_amount | Numeric(10,2) | not null |
| commission_rate | Numeric(5,4) | default 0.03 (3%) |
| is_active | Boolean | default True |
| is_default | Boolean | default False |
| minimum_charge | Numeric(10,2) | nullable |
| proration_enabled | Boolean | default True |
| effective_from | TIMESTAMP | not null |
| effective_to | TIMESTAMP | nullable |

**Unique Index:** `(subscription_plan_id, currency, is_default)`

#### ShopSubscription (Table: `shop_subscriptions`)

**File:** `app/core/database/models/shop_subscription.py`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_id | String | FK -> shops.id |
| subscription_type | SubscriptionType enum | default TRIAL |
| status | SubscriptionStatus enum | default ACTIVE |
| subscription_plan_id | String(255) | FK -> subscription_plans.id |
| pricing_tier_id | String(255) | FK -> pricing_tiers.id |
| trial_threshold_override | Numeric(10,2) | nullable |
| trial_duration_days | Integer | nullable |
| user_chosen_cap_amount | Numeric(10,2) | nullable |
| auto_renew | Boolean | default True |
| shopify_subscription_id | String(255) | nullable |
| shopify_line_item_id | String(255) | nullable |
| shopify_status | String(50) | nullable |
| confirmation_url | Text | nullable |
| started_at | TIMESTAMP | not null |
| completed_at | TIMESTAMP | nullable |
| cancelled_at | TIMESTAMP | nullable |
| expires_at | TIMESTAMP | nullable |
| is_active | Boolean | default True |
| shop_subscription_metadata | JSONB | nullable |

**Properties:**
- `effective_trial_threshold`: from pricing tier or override (default $75.00)
- `effective_commission_rate`: from pricing tier (default 3%)
- `currency`: from pricing tier (default "USD")
- `effective_cap_amount`: user choice or trial threshold

#### BillingCycle (Table: `billing_cycles`)

**File:** `app/core/database/models/billing_cycle.py`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_subscription_id | String(255) | FK -> shop_subscriptions.id |
| cycle_number | Integer | not null |
| start_date | TIMESTAMP | not null |
| end_date | TIMESTAMP | not null |
| initial_cap_amount | Numeric(10,2) | not null |
| current_cap_amount | Numeric(10,2) | not null |
| usage_amount | Numeric(10,2) | default 0.00 |
| commission_count | Integer | default 0 |
| status | BillingCycleStatus enum | default ACTIVE |
| activated_at | TIMESTAMP | nullable |
| completed_at | TIMESTAMP | nullable |
| cancelled_at | TIMESTAMP | nullable |

**Unique Index:** `(shop_subscription_id, status)` -- one active cycle per subscription

**Properties:** `is_active`, `is_completed`, `is_cancelled`, `usage_percentage`, `remaining_cap`, `is_cap_reached`, `is_near_cap(threshold=0.8)`, `days_remaining`, `has_cap_increase`, `cap_increase_amount`

#### BillingInvoice (Table: `billing_invoices`)

**File:** `app/core/database/models/billing_invoice.py`

| Column | Type | Notes |
|--------|------|-------|
| id | String | PK, UUID |
| shop_subscription_id | String(255) | FK -> shop_subscriptions.id |
| shopify_invoice_id | String(255) | unique |
| invoice_number | String(100) | nullable |
| amount_due | Numeric(10,2) | default 0.00 |
| amount_paid | Numeric(10,2) | default 0.00 |
| total_amount | Numeric(10,2) | default 0.00 |
| currency | String(3) | default "USD" |
| invoice_date | TIMESTAMP | not null |
| due_date | TIMESTAMP | nullable |
| paid_at | TIMESTAMP | nullable |
| status | InvoiceStatus enum | default PENDING |
| description | Text | nullable |
| line_items | JSON | nullable |
| shopify_response | JSON | nullable |
| payment_method | String(100) | nullable |
| failure_reason | String(500) | nullable |

#### CommissionRecord (Table: `commission_records`)

**File:** `app/core/database/models/commission.py`

| Column | Type | Notes |
|--------|------|-------|
| id | String(255) | PK, UUID |
| shop_id | String(255) | FK -> shops.id |
| purchase_attribution_id | String(255) | FK -> purchase_attributions.id, unique |
| billing_cycle_id | String(255) | FK -> billing_cycles.id, nullable |
| order_id | String(255) | not null |
| order_date | DateTime(tz) | not null |
| attributed_revenue | Numeric(10,2) | not null |
| commission_rate | Numeric(5,4) | default 0.03 |
| commission_earned | Numeric(10,2) | not null |
| commission_charged | Numeric(10,2) | default 0 |
| commission_overflow | Numeric(10,2) | default 0 |
| billing_cycle_start | DateTime(tz) | nullable |
| billing_cycle_end | DateTime(tz) | nullable |
| cycle_usage_before | Numeric(10,2) | default 0 |
| cycle_usage_after | Numeric(10,2) | default 0 |
| capped_amount | Numeric(10,2) | not null |
| trial_accumulated | Numeric(10,2) | default 0 |
| billing_phase | BillingPhase enum | default TRIAL |
| status | CommissionStatus enum | default TRIAL_PENDING |
| charge_type | ChargeType enum | default TRIAL |
| shopify_usage_record_id | String(255) | nullable, unique |
| shopify_recorded_at | DateTime(tz) | nullable |
| shopify_response | JSON | nullable |
| currency | String(3) | default "USD" |
| notes | Text | nullable |
| commission_metadata | JSON | nullable |
| error_count | Integer | default 0 |
| last_error | Text | nullable |
| last_error_at | DateTime(tz) | nullable |
| deleted_at | DateTime(tz) | nullable |

**Properties:** `is_trial`, `is_charged`, `has_overflow`, `is_partial_charge`, `charge_percentage`

**Unique Constraint:** `purchase_attribution_id` (one commission per attribution)

---

## Known Bugs Summary

1. **JWT Service (line 200-203):** `refresh_access_token()` references `refresh_result["subscription_status"]` but the token payload uses `is_service_active` as the key. This would cause a `KeyError`. The method does not appear to be called in the codebase -- the controller uses a different flow.

2. **Recommendation Cache (all TTLs = 0):** All `CACHE_TTL` values in `app/recommandations/cache.py` are set to 0, effectively disabling all recommendation caching. This means every recommendation request hits Gorse/FP-Growth/DB with no caching layer.

3. **Billing Consumer Stub:** `app/consumers/kafka/billing_consumer.py` `_handle_message()` only logs the message but does not process any billing events. All billing logic comments are TODOs.

4. **Directory Name Typo:** The recommendation engine directory is named `recommandations` (French spelling) instead of `recommendations`. This is not a runtime bug but a maintenance concern.
