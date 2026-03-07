# BetterBundle Kafka and Infrastructure - Detailed Reference

This document provides an exhaustive reference for all Kafka topics, Docker Compose services, Gorse configuration, Redis usage, and environment variables in the BetterBundle system.

---

## Table of Contents

1. [Kafka Topics](#kafka-topics)
2. [Kafka Producers](#kafka-producers)
3. [Kafka Consumers](#kafka-consumers)
4. [Docker Compose Services](#docker-compose-services)
5. [Gorse Configuration](#gorse-configuration)
6. [Redis Key Patterns](#redis-key-patterns)
7. [Environment Variables](#environment-variables)

---

## Kafka Topics

All topic configurations are defined in two places:
- **Node.js**: `/better-bundle/app/utils/kafka-config.ts`
- **Python**: `/python-worker/app/core/config/kafka_settings.py`

### Topic: `shopify-events`

| Property | Value |
|----------|-------|
| Partitions | 6 |
| Replication Factor | 3 |
| Retention | 604800000ms (7 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `shopify-events-processors` |

**Purpose**: Receives all Shopify webhook events (product, order, customer, collection CRUD events).

### Topic: `data-collection-jobs`

| Property | Value |
|----------|-------|
| Partitions | 4 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `data-collection-processors` |

**Purpose**: Triggers for Shopify data collection tasks (initial backfill, incremental sync).

### Topic: `normalization-jobs`

| Property | Value |
|----------|-------|
| Partitions | 4 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `normalization-processors` |

**Purpose**: Data normalization tasks converting raw Shopify data to normalized tables.

### Topic: `billing-events`

| Property | Value |
|----------|-------|
| Partitions | 4 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `billing-processors` |

**Purpose**: Billing lifecycle events (plan changes, suspension, notifications).

### Topic: `shopify-usage-events`

| Property | Value |
|----------|-------|
| Partitions | 4 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `shopify-usage-processors` |

**Purpose**: Shopify usage record creation, cap increases, rejected commission reprocessing.

### Topic: `feature-computation-jobs`

| Property | Value |
|----------|-------|
| Partitions | 2 |
| Replication Factor | 3 |
| Retention | 86400000ms (1 day) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `feature-computation-processors` |

**Purpose**: ML feature engineering pipeline triggers.

### Topic: `customer-linking-jobs`

| Property | Value |
|----------|-------|
| Partitions | 4 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `customer-linking-processors` |

**Purpose**: Customer identity resolution and cross-session linking.

### Topic: `purchase-attribution-jobs`

| Property | Value |
|----------|-------|
| Partitions | 6 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `purchase-attribution-processors` |

**Purpose**: Purchase attribution processing linking orders to extension interactions.

### Topic: `ml-training` (Node.js only)

| Property | Value |
|----------|-------|
| Partitions | 2 |
| Replication Factor | 3 |
| Retention | 86400000ms (1 day) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `ml-training-processors` |

**Purpose**: ML model training triggers (defined in Node.js config but no active consumer found).

### Topic: `behavioral-events` (Node.js only)

| Property | Value |
|----------|-------|
| Partitions | 8 |
| Replication Factor | 3 |
| Retention | 259200000ms (3 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `behavioral-events-processors` |

**Purpose**: User behavioral events (defined in Node.js config but no active consumer found).

### Topic: `access-control`

| Property | Value |
|----------|-------|
| Partitions | 6 |
| Replication Factor | 3 |
| Retention | 604800000ms (7 days) |
| Compression | snappy |
| Cleanup Policy | delete |
| Consumer Group | `access-control-processors` |

**Purpose**: Access control events for shop service suspension and reactivation.

---

## Kafka Producers

All producers are in the Remix/Node.js application. The Python worker only consumes.

### Producer: `KafkaProducerService`

**File**: `/better-bundle/app/services/kafka/kafka-producer.service.ts`

**Client Configuration** (from `/better-bundle/app/services/kafka/kafka-client.service.ts`):
- `maxInFlightRequests`: 1
- `idempotent`: true
- `transactionTimeout`: 30000ms
- Retry: `initialRetryTime` 100ms, `retries` 8

#### Method: `publishShopifyEvent()`

| Property | Value |
|----------|-------|
| Topic | `shopify-events` |
| Partition Key | `shop_id` or `shop_domain` |
| Line | `kafka-producer.service.ts:96` |

**Message Schema**:
```json
{
  "event_type": "product_updated | product_created | product_deleted | collection_updated | collection_created | collection_deleted | order_paid | order_updated | refund_created | customer_created | customer_updated | inventory_updated",
  "shop_id": "string (optional)",
  "shop_domain": "string (optional)",
  "shopify_id": "string",
  "timestamp": "ISO 8601 string",
  "worker_id": "string",
  "source": "shopify_webhook"
}
```

**Headers**: `event-type`, `shop-id`, `timestamp`

#### Method: `publishDataJobEvent()`

| Property | Value |
|----------|-------|
| Topic | `data-collection-jobs` |
| Partition Key | `shop_id` |
| Line | `kafka-producer.service.ts:144` |

**Message Schema**:
```json
{
  "job_type": "string",
  "shop_id": "string",
  "event_type": "data_collection",
  "job_id": "string",
  "collection_payload": {
    "data_types": ["products", "orders", "customers", "collections"],
    "specific_ids": {}
  },
  "timestamp": "ISO 8601 string",
  "worker_id": "string",
  "source": "data_collection"
}
```

**Headers**: `job-type`, `shop-id`, `timestamp`

**Caller**: `onboarding.service.ts:375` triggers data collection after shop onboarding.

#### Method: `publishShopifyUsageEvent()`

| Property | Value |
|----------|-------|
| Topic | `shopify-usage-events` |
| Partition Key | `shop_id` or `commission_id` or `shop_domain` |
| Line | `kafka-producer.service.ts:197` |

**Message Schema**:
```json
{
  "event_type": "record_usage | cap_increase | reprocess_rejected_commissions",
  "shop_id": "string",
  "commission_id": "string (for record_usage)",
  "billing_cycle_id": "string (for cap_increase/reprocess)",
  "new_cap_amount": "number (for cap_increase)",
  "timestamp": "ISO 8601 string",
  "worker_id": "string",
  "source": "shopify_usage"
}
```

**Headers**: `event-type`, `shop-id`, `timestamp`

#### Method: `publishAccessControlEvent()`

| Property | Value |
|----------|-------|
| Topic | `access-control` |
| Partition Key | `shop_id` |
| Line | `kafka-producer.service.ts:251` |

**Message Schema**:
```json
{
  "event_type": "string",
  "shop_id": "string",
  "timestamp": "ISO 8601 string",
  "worker_id": "string",
  "source": "access_control"
}
```

**Headers**: `event-type`, `shop-id`, `timestamp`

#### Method: `publishBatch()`

| Property | Value |
|----------|-------|
| Topic | Variable (per event) |
| Line | `kafka-producer.service.ts:280` |

Publishes multiple events sequentially, each to its own specified topic.

---

## Kafka Consumers

All consumers are in the Python worker application at `/python-worker/app/consumers/kafka/`.

### Consumer: `DataCollectionKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/data_collection_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `data-collection-jobs`, `shopify-events` |
| Group ID | `data-collection-processors` |
| Auto Commit | No (manual commit after processing) |

**Event Types Handled**:
- `data_collection` - Full data collection jobs (backfill/incremental)
- `product_updated`, `product_created`, `product_deleted` - Product webhooks
- `collection_updated`, `collection_created`, `collection_deleted` - Collection webhooks
- `order_paid`, `order_updated`, `refund_created` - Order webhooks
- `customer_created`, `customer_updated` - Customer webhooks
- `inventory_updated` - Inventory webhooks

**Processing Logic**:
1. Resolves shop data (by `shop_id` for data collection, by `shop_domain` for webhooks)
2. Checks if shop is active; sends to DLQ if suspended
3. For data collection: calls `shopify_service.collect_all_data()` with collection payload
4. For webhooks: converts event to data collection payload, then collects specific entities
5. For deletion events: delegates to `NormalizationService.deletion_service`

### Consumer: `NormalizationKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/normalization_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `normalization-jobs` |
| Group ID | `normalization-processors` |
| Auto Commit | No |

**Event Types Handled**:
- `normalize_data` - Unified normalization handler

**Processing Logic**:
1. Validates `shop_id` and checks shop is active (DLQ if suspended)
2. Calls `NormalizationService.normalize_data(shop_id, data_type, params)`
3. On success, triggers feature computation for the data type
4. For order-related data, triggers FBT (Frequently Bought Together) model retraining in background

### Consumer: `FeatureComputationKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/feature_computation_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `feature-computation-jobs` |
| Group ID | `feature-computation-processors` |
| Auto Commit | No |

**Event Types Handled**:
- Messages with `job_id`, `shop_id`, `features_ready`, and `metadata`

**Processing Logic**:
1. Validates `job_id` and `shop_id`; checks shop is active
2. If `features_ready` is false, runs comprehensive feature engineering pipeline
3. Calls `FeatureEngineeringService.run_comprehensive_pipeline_for_shop()`

### Consumer: `BillingKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/billing_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `billing-events` |
| Group ID | `billing-processors` |
| Auto Commit | No |

**Event Types Handled**:
- Generic billing events (placeholder for billing status updates, suspension, notifications)

**Processing Logic**:
1. Extracts `event_type`, `shop_id`, `plan_id`
2. Logs the event (handler logic is a placeholder for future billing event processing)

### Consumer: `CustomerLinkingKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/customer_linking_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `customer-linking-jobs` |
| Group ID | `customer-linking-processors` |
| Auto Commit | No |

**Event Types Handled**:
- `customer_linking` - Customer identity resolution
- `cross_session_linking` - Cross-session linking
- `backfill_interactions` - Backfill customer_id on anonymous interactions

**Processing Logic**:
1. Validates required fields (`job_id`, `shop_id`, `customer_id`); checks shop is active
2. For `customer_linking`: runs `CrossSessionLinkingService.link_customer_sessions()`, then backfills interactions
3. For `cross_session_linking`: runs cross-session linking only
4. For `backfill_interactions`: updates `user_interactions` with missing `customer_id`, fires feature computation

### Consumer: `PurchaseAttributionKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/purchase_attribution_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `purchase-attribution-jobs` |
| Group ID | `purchase-attribution-processors` |
| Auto Commit | No |

**Event Types Handled**:
- `purchase_ready_for_attribution` - Orders ready for attribution processing

**Processing Logic**:
1. Validates `shop_id` and `order_id`; checks shop is active (DLQ if suspended)
2. Loads normalized `order_data` and `line_item_data` from database
3. Checks order metafields for session ID (`bb_recommendation` namespace)
4. Finds most recent user session for the customer
5. Checks for tracking data from extensions (Phoenix line item properties, Apollo/Mercury metafields)
6. Checks for extension interactions (phoenix, venus, apollo) in last 30 days
7. Constructs `PurchaseEvent` and calls `BillingServiceV2.process_purchase_attribution()`

### Consumer: `ShopifyUsageKafkaConsumer`

**File**: `/python-worker/app/consumers/kafka/shopify_usage_consumer.py`

| Property | Value |
|----------|-------|
| Topics | `shopify-usage-events` |
| Group ID | `shopify-usage-processors` |
| Auto Commit | No |

**Event Types Handled**:
- `record_usage` - Record commission as Shopify usage record
- `cap_increase` - Handle cap increase, reprocess rejected commissions
- `reprocess_rejected_commissions` - Explicit reprocess of rejected commissions

**Processing Logic**:
1. For `record_usage`: calls `CommissionServiceV2.record_commission_to_shopify()` for a specific commission ID
2. For `cap_increase`: reprocesses rejected/pending commissions, reactivates suspended subscriptions
3. For `reprocess_rejected_commissions`: re-evaluates charge amounts based on current cap, re-records to Shopify
4. Reprocessing recalculates `commission_charged`, `commission_overflow`, and `charge_type` for each commission

---

## Docker Compose Services

Three compose files exist:
- **Dev**: `/docker-compose.dev.yml` - Development with all services
- **Local**: `/docker-compose.local.yml` - Local development (similar to dev, with Promtail resource limits)
- **Prod**: `/docker-compose.prod.yml` - Production with resource limits, networks, nginx proxy

### Service: `postgres`

| Property | Dev | Prod |
|----------|-----|------|
| Image | `postgres:17` | `postgres:17` |
| Container | `betterbundle-postgres-dev` | `betterbundle-postgres` |
| Port | `5432:5432` | `5432:5432` |
| Volume | `postgres_data:/var/lib/postgresql/data` | `postgres_data:/var/lib/postgresql/data` |
| Env File | `.env.dev` | `.env.prod` |
| Restart | `unless-stopped` | `unless-stopped` |
| CPU Limit | - | 1.0 |
| Memory Limit | - | 512M |
| Health Check | `pg_isready -U postgres` (10s interval, 5s timeout, 5 retries) | Same |
| Networks | default | `frontend`, `backend` |

### Service: `kafka_b` / `kafka`

| Property | Dev (`kafka_b`) | Prod (`kafka`) |
|----------|-----------------|----------------|
| Image | `confluentinc/cp-kafka:7.8.0` | `confluentinc/cp-kafka:7.8.0` |
| Container | `kafka_b_dev` | `betterbundle-kafka` |
| Port | `9092:9092` | `127.0.0.1:9092:9092` |
| Volume | `kafka_data:/var/lib/kafka/data` | `kafka_data:/var/lib/kafka/data` |
| CPU Limit | - | 1.0 |
| Memory Limit | - | 1G |

**Kafka Environment Variables**:
| Variable | Dev Value | Prod Value |
|----------|-----------|------------|
| `KAFKA_NODE_ID` | 1 | 1 |
| `KAFKA_PROCESS_ROLES` | `broker,controller` | `broker,controller` |
| `KAFKA_CONTROLLER_QUORUM_VOTERS` | `1@kafka_b:29093` | `1@kafka:29093` |
| `KAFKA_LISTENERS` | `PLAINTEXT://0.0.0.0:9093,CONTROLLER://0.0.0.0:29093,PLAINTEXT_HOST://0.0.0.0:9092` | `PLAINTEXT://kafka:29092,CONTROLLER://kafka:29093,PLAINTEXT_HOST://0.0.0.0:9092` |
| `KAFKA_ADVERTISED_LISTENERS` | `PLAINTEXT://kafka_b:9093,PLAINTEXT_HOST://localhost:9092` | `PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092` |
| `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` | `CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT` | Same |
| `KAFKA_INTER_BROKER_LISTENER_NAME` | `PLAINTEXT` | `PLAINTEXT` |
| `KAFKA_CONTROLLER_LISTENER_NAMES` | `CONTROLLER` | `CONTROLLER` |
| `KAFKA_LOG_DIRS` | `/var/lib/kafka/data` | `/var/lib/kafka/data` |
| `CLUSTER_ID` | `MkU3OEVBNTcwNTJENDM2Qk` | `MkU3OEVBNTcwNTJENDM2Qk` |
| `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` | 1 | 1 |
| `KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS` | 0 | - |
| `KAFKA_TRANSACTION_STATE_LOG_MIN_ISR` | 1 | 1 |
| `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR` | 1 | 1 |
| `KAFKA_AUTO_CREATE_TOPICS_ENABLE` | true | true |
| `KAFKA_NUM_PARTITIONS` | - | 4 |
| `KAFKA_DEFAULT_REPLICATION_FACTOR` | - | 1 |
| `KAFKA_LOG_RETENTION_HOURS` | - | 168 (7 days) |
| `KAFKA_LOG_RETENTION_BYTES` | - | 1073741824 (1GB) |

**Health Check**: `kafka-broker-api-versions --bootstrap-server localhost:9092` (30s interval, 10s timeout, 5 retries, 40s start period)

### Service: `kafka-ui`

| Property | Dev | Prod |
|----------|-----|------|
| Image | `provectuslabs/kafka-ui:latest` | `provectuslabs/kafka-ui:latest` |
| Port | `8080:8080` | `127.0.0.1:8080:8080` |
| Cluster Name | `local-kafka-kraft` | `production-kafka-kraft` |
| Bootstrap Servers | `kafka_b:9093` | `kafka:29092` |
| CPU Limit | - | 0.5 |
| Memory Limit | - | 256M |

### Service: `rest-proxy`

| Property | Dev | Prod |
|----------|-----|------|
| Image | `confluentinc/cp-kafka-rest:latest` | Same |
| Port | `8082:8082` | `127.0.0.1:8082:8082` |
| Bootstrap Servers | `kafka_b:9093` | `kafka:29092` |
| CPU Limit | - | 0.5 |
| Memory Limit | - | 256M |
| Health Check (prod) | - | `curl -f http://localhost:8082/` (30s interval) |

### Service: `redis`

| Property | Dev | Prod |
|----------|-----|------|
| Image | `redis/redis-stack:7.2.0-v18` | `redis/redis-stack:7.2.0-v18` |
| Container | `betterbundle-redis-dev` | `betterbundle-redis` |
| Ports | `6379:6379`, `8002:8001` | `6379:6379`, `8002:8001` |
| Volume | `redis_data:/data` | `redis_data:/data` |
| Max Memory | 256mb (dev) | 512mb (prod) |
| Eviction Policy | `allkeys-lru` | `allkeys-lru` |
| Append Only | yes | yes |
| Append Fsync | `everysec` | `everysec` |
| CPU Limit | - | 0.5 |
| Memory Limit | - | 256M |
| Health Check | `redis-cli -a <password> ping` (5s interval, 3s timeout) | Same (with conditional password) |

### Service: `gorse`

| Property | Dev | Prod |
|----------|-----|------|
| Image | `zhenghaoz/gorse-in-one:latest` | Same |
| Container | `betterbundle-gorse-dev` | `betterbundle-gorse` |
| Ports | `8086:8086`, `8088:8088` | `127.0.0.1:8086:8086`, `127.0.0.1:8088:8088` |
| Config | `./config.toml:/etc/gorse/config.toml` | Same (read-only in prod) |
| Volumes | `gorse_logs:/var/log/gorse`, `gorse_cache:/var/lib/gorse` | Same |
| CPU Limit | - | 2.0 |
| Memory Limit | - | 2G |
| Depends On | `postgres` (healthy), `redis` (healthy) | Same |

### Service: `python-worker`

| Property | Dev | Prod |
|----------|-----|------|
| Build Context | `./python-worker` (Dockerfile.dev) | `./python-worker` (Dockerfile.prod) |
| Container | `betterbundle-python-worker-dev` | `betterbundle-python-worker` |
| Port | `8000:8000` | `127.0.0.1:8000:8000` |
| Volumes | `./python-worker:/app` (hot reload) | None (built image) |
| CPU Limit | - | 2.0 |
| Memory Limit | - | 2G |
| Depends On | `postgres`, `redis`, `kafka_b`, `gorse` | Same |
| Health Check | `curl -f http://localhost:8000/health` (30s interval, 60s start period) | Same |

### Service: `remix-app` (Prod only)

| Property | Value |
|----------|-------|
| Build Context | `./better-bundle` (Dockerfile.prod) |
| Container | `betterbundle-remix` |
| Port | `127.0.0.1:3000:3000` |
| CPU Limit | 1.0 |
| Memory Limit | 1G |
| Depends On | postgres, redis, kafka, gorse, python-worker |
| Health Check | `curl -f http://localhost:3000/` (30s interval, 60s start period) |
| Networks | `frontend`, `backend` |

### Service: `admin` (Prod only)

| Property | Value |
|----------|-------|
| Build Context | `./admin` (Dockerfile) |
| Container | `betterbundle-admin` |
| Port | `127.0.0.1:8003:8000` |
| CPU Limit | 1.0 |
| Memory Limit | 1G |
| Depends On | postgres, redis, kafka |
| Networks | `frontend`, `backend` |

### Logging Stack

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `loki` | `grafana/loki:3.4.1` | `3100` | Log aggregation |
| `promtail` | `grafana/promtail:3.4.1` | - | Log collector, reads Docker containers |
| `grafana` | `grafana/grafana:11.4.0` | `3001:3000` | Visualization, has `redis-datasource` plugin |

**Grafana environment (prod)**:
- `GF_SECURITY_ADMIN_USER=admin`
- `GF_USERS_ALLOW_SIGN_UP=false`
- `GF_INSTALL_PLUGINS=redis-datasource`

### Service: `nginx-proxy-manager` (Prod only)

| Property | Value |
|----------|-------|
| Image | `jc21/nginx-proxy-manager:latest` |
| Ports | `80:80`, `443:443`, `81:81` |
| Volumes | `npm_data:/data`, `npm_letsencrypt:/etc/letsencrypt` |
| CPU Limit | 0.5 |
| Memory Limit | 256M |
| Networks | `frontend`, `backend` |

### Networks (Prod)

| Network | Driver | Internal |
|---------|--------|----------|
| `frontend` | bridge | false |
| `backend` | bridge | false |

### Volumes

| Volume | Used By |
|--------|---------|
| `postgres_data` | postgres |
| `redis_data` | redis |
| `kafka_data` | kafka |
| `gorse_logs` | gorse |
| `gorse_cache` | gorse |
| `loki_data` | loki |
| `grafana_data` | grafana |
| `npm_data` | nginx-proxy-manager (prod) |
| `npm_letsencrypt` | nginx-proxy-manager (prod) |

---

## Gorse Configuration

**File**: `/config.toml`

### [database]

| Setting | Value | Description |
|---------|-------|-------------|
| `cache_store` | `${GORSE_CACHE_STORE}` | Redis connection for cache (resolves to `redis://redis:6379/0`) |
| `data_store` | `${GORSE_DATA_STORE}` | PostgreSQL connection for data |

### [database.mysql]

| Setting | Value |
|---------|-------|
| `isolation_level` | `READ-UNCOMMITTED` |

### [master]

| Setting | Value | Description |
|---------|-------|-------------|
| `port` | 8086 | gRPC port for master |
| `host` | `0.0.0.0` | Bind address |
| `http_port` | 8088 | HTTP API port |
| `http_host` | `0.0.0.0` | HTTP bind address |
| `n_jobs` | 8 | Number of parallel jobs |
| `meta_timeout` | `120s` | Metadata operation timeout |

### [server]

| Setting | Value | Description |
|---------|-------|-------------|
| `default_n` | 25 | Default number of recommendations |
| `api_key` | `${GORSE_API_KEY}` | API authentication key |
| `cache_expire` | `2h` | Server-side cache expiration |
| `auto_insert_user` | true | Auto-create users on feedback |
| `auto_insert_item` | true | Auto-create items on feedback |

### [recommend]

| Setting | Value | Description |
|---------|-------|-------------|
| `cache_size` | 100000 | Recommendation cache size |
| `cache_expire` | `4h` | Recommendation cache TTL |
| `active_user_ttl` | 0 | Active user TTL (0 = never expire) |
| `enable_hot_recommend` | true | Enable hot/trending recommendations |
| `enable_latest_recommend` | true | Enable latest item recommendations |
| `enable_user_based_recommend` | true | Enable user-based collaborative filtering |
| `enable_item_based_recommend` | true | Enable item-based collaborative filtering |
| `enable_collaborative_recommend` | true | Enable collaborative filtering |

### [recommend.data_source]

**Positive Feedback Types** (strong buy signals):
- `purchase`
- `high_value_purchase`
- `checkout_completed`
- `ready_to_buy`
- `strong_affinity`
- `conversion_session`
- `search_conversion`

**Read Feedback Types** (engagement signals):
- `product_viewed`
- `product_added_to_cart`
- `checkout_started`
- `progressing_interest`
- `high_engagement_session`
- `search_engagement`
- `basic_interest`

**Negative Feedback Types** (disinterest signals):
- `refund`
- `product_removed_from_cart`
- `bounce`
- `session_bounce`
- `recommendation_declined`
- `recommendation_declined_high_confidence`
- `recommendation_declined_similar`

| Setting | Value |
|---------|-------|
| `positive_feedback_ttl` | 0 (never expire) |
| `item_ttl` | 0 (never expire) |

### [recommend.popular]

| Setting | Value | Description |
|---------|-------|-------------|
| `popular_window` | `168h` | 7-day window for popularity |

### [recommend.collaborative]

| Setting | Value | Description |
|---------|-------|-------------|
| `enable_index` | true | Enable HNSW index |
| `index_recall` | 0.90 | Index recall target |
| `index_fit_epoch` | 200 | Epochs for index fitting |
| `model_fit_period` | `45m` | Model retraining interval |
| `model_search_period` | `3h` | Hyperparameter search interval |
| `model_search_epoch` | 75 | Epochs per search trial |
| `model_search_trials` | 30 | Number of search trials |
| `enable_model_size_search` | true | Auto model size search |

### [recommend.ranking]

| Setting | Value | Description |
|---------|-------|-------------|
| `model` | `fm` | Factorization Machine ranking model |
| `factors` | 64 | Latent factor dimension |
| `epochs` | 40 | Training epochs |
| `learning_rate` | 0.003 | Learning rate |
| `reg` | 0.01 | Regularization |
| `alpha` | 0.01 | Alpha parameter |
| `enable_user_features` | true | Use user features for ranking |
| `enable_item_features` | true | Use item features for ranking |
| `fit_period` | `45m` | Retraining interval |
| `search_period` | `3h` | Hyperparameter search interval |
| `search_trials` | 30 | Search trials |
| `search_epoch` | 30 | Epochs per search trial |

### [recommend.replacement]

| Setting | Value | Description |
|---------|-------|-------------|
| `enable_replacement` | true | Enable recommendation replacement |
| `positive_replacement_decay` | 0.80 | Decay rate for positive feedback |
| `read_replacement_decay` | 0.65 | Decay rate for read feedback |

### [recommend.offline]

| Setting | Value | Description |
|---------|-------|-------------|
| `check_recommend_period` | `20m` | Check interval for stale recommendations |
| `refresh_recommend_period` | `8h` | Full refresh interval |
| `enable_latest_recommend` | true | Include latest items |
| `enable_popular_recommend` | true | Include popular items |
| `enable_user_based_recommend` | true | Include user-based CF |
| `enable_item_based_recommend` | true | Include item-based CF |
| `enable_collaborative_recommend` | true | Include collaborative |
| `enable_click_through_prediction` | true | Enable CTR prediction |

### [recommend.online]

| Setting | Value | Description |
|---------|-------|-------------|
| `fallback_recommend` | `["collaborative", "item_based", "user_based", "popular", "latest"]` | Fallback order |
| `num_feedback_fallback_item_based` | 15 | Feedback threshold for item-based fallback |
| `enable_realtime_recommend` | true | Enable realtime recommendations |
| `enable_session_recommend` | true | Enable session-based recommendations |
| `session_recommend_cache_size` | 2000 | Session recommendation cache entries |
| `session_recommend_cache_expire` | `45m` | Session cache TTL |

### [tracing]

| Setting | Value |
|---------|-------|
| `enable_tracing` | false |

### [experimental]

| Setting | Value |
|---------|-------|
| `enable_deep_learning` | false |
| `deep_learning_batch_size` | 512 |

### [oidc]

| Setting | Value |
|---------|-------|
| `enable` | false |

### [opentelemetry]

| Setting | Value |
|---------|-------|
| `enabled` | false |

---

## Redis Key Patterns

Redis is used across the system with database index 0 (infrastructure) and 1 (application).

### Key Pattern: `cache:{namespace}:{key}:{param_hash}:value`
### Key Pattern: `cache:{namespace}:{key}:{param_hash}:metadata`

The `RedisCacheService` at `/python-worker/app/shared/services/redis_cache.py` stores all cache entries as two keys: a `:value` key with serialized JSON data and a `:metadata` key with access statistics and TTL info. Both use `SETEX` with TTL.

### Namespace: `shop_lookup`

**Service**: `ShopCacheService` at `/python-worker/app/services/shop_cache_service.py`

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `cache:shop_lookup:active_shop:{hash}:value` | 300s (5 min) | Cached shop data (id, domain, is_active, plan_type, currency_code, access_token, last_analysis_at) |
| `cache:shop_lookup:active_shop:{hash}:metadata` | 300s (5 min) | Cache metadata (created_at, ttl, access_count) |
| `cache:shop_lookup:negative_shop:{hash}:value` | 150s (2.5 min) | Negative cache (shop not found) |
| `cache:shop_lookup:negative_shop:{hash}:metadata` | 150s (2.5 min) | Negative cache metadata |

### Namespace: `permissions`

**Service**: `ShopifyPermissionService` at `/python-worker/app/domains/shopify/services/permission_service.py`

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `cache:permissions:{key}:{hash}:value` | 3600s (1 hour) | Cached shop permission results |
| `cache:permissions:{key}:{hash}:metadata` | 3600s (1 hour) | Permission cache metadata |

### Recommendation Cache

**Service**: `RecommendationCacheService` at `/python-worker/app/recommandations/cache.py`

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `rec:{md5_hash}` | Currently 0 (disabled) | Recommendation results keyed by MD5 of `recommendations:{shop_id}:{context}:{product_ids}:{user_id}:{session_id}:{category}:{limit}:{exclude_items}` |

**Context-specific TTLs** (all currently set to 0 / disabled):
- `product_page`: 0s
- `homepage`: 0s
- `cart`: 0s
- `profile`: 0s
- `checkout`: 0s
- `order_history`: 0s
- `order_status`: 0s
- `post_purchase`: 0s

### Product Category Cache

**Service**: `CategoryDetectionService` at `/python-worker/app/recommandations/category_detection.py`

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `product_category:{shop_id}:{product_id}` | 3600s (1 hour) | Detected product category string |

### Gorse Internal Cache

Gorse uses Redis DB 0 internally for its own caching:
- Recommendation cache (controlled by `cache_expire = 2h` in `[server]` and `cache_expire = 4h` in `[recommend]`)
- Session recommendation cache (2000 entries, 45m TTL)

---

## Environment Variables

### Shared Infrastructure Variables

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `NODE_ENV` | `development` | `production` | Remix app |
| `DEBUG` | `true` | `false` | Both |
| `LOG_LEVEL` | `debug` | `info` | Both |
| `HOT_RELOAD` | `true` | `false` | Remix app |

### Database

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/betterbundle` | `postgresql://postgres:<password>@postgres:5432/betterbundle` | Remix (Prisma), Python worker |
| `POSTGRES_DB` | `betterbundle` | `betterbundle` | Docker postgres |
| `POSTGRES_USER` | `postgres` | `postgres` | Docker postgres |
| `POSTGRES_PASSWORD` | `postgres` | `<production password>` | Docker postgres |

### Redis

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `REDIS_URL` | `redis://redis:6379` | `redis://redis:6379` | Both |
| `REDIS_HOST` | `redis` / `localhost` | `redis` | Both |
| `REDIS_PORT` | `6379` | `6379` | Both |
| `REDIS_PASSWORD` | (empty) | (empty) | Both |
| `REDIS_DB` | `0` (infra) / `1` (app) | `0` | Both |
| `REDIS_TLS` | `false` | - | Python worker |

### Kafka

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka_b:9093` | `betterbundle-kafka:29092` | Both |
| `KAFKA_BROKERS` | - | `betterbundle-kafka:29092` | Remix app |
| `KAFKA_CLIENT_ID` | `betterbundle` (default) | `betterbundle` (default) | Both |
| `KAFKA_WORKER_ID` | `worker-1` (default) | `worker-1` (default) | Both |
| `KAFKA_GROUP_INSTANCE_ID` | `betterbundle-worker-1` (default) | Same | Python worker |
| `KAFKA_HEALTH_CHECK_INTERVAL` | `30` (default) | Same | Python worker |
| `KAFKA_HEALTH_CHECK_TIMEOUT` | `5` (default) | Same | Python worker |

### Gorse

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `GORSE_API_URL` / `GORSE_BASE_URL` | `http://gorse:8088` / `http://localhost:8088` | `http://gorse:8088` | Both |
| `GORSE_API_KEY` | `secure_random_key_123` | `<production key>` | Both, config.toml |
| `GORSE_MASTER_KEY` | (empty) | - | Python worker |
| `GORSE_LOG_LEVEL` | `debug` | `info` | Gorse |
| `GORSE_CACHE_STORE` | `redis://redis:6379/0` | `redis://redis:6379/0` | config.toml |
| `GORSE_DATA_STORE` | `postgresql://postgres:postgres@postgres:5432/betterbundle?sslmode=disable` | `postgresql://postgres:<password>@postgres:5432/betterbundle?sslmode=disable` | config.toml |
| `GORSE_MASTER_HOST` | `0.0.0.0` | `0.0.0.0` | config.toml |
| `ENABLE_GORSE_SYNC` | `true` | - | Python worker |

### Shopify

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `SHOPIFY_API_KEY` | `<dev key>` | `<prod key>` | Remix app |
| `SHOPIFY_API_SECRET` | `<dev secret>` | `<prod secret>` | Remix app |
| `SHOPIFY_APP_URL` | `https://<cloudflare tunnel>` | `https://betterbundle.site` | Remix app |
| `SCOPES` / `SHOPIFY_SCOPES` | (long comma-separated list) | Same | Remix app |
| `SHOPIFY_ACCESS_TOKEN` | `shpat_...` | - | Python worker (fallback) |
| `SHOPIFY_APP_URL` (worker) | `http://localhost:3000` | - | Python worker |

### Monitoring

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `LOKI_URL` | `http://loki:3100` | `http://betterbundle-loki:3100` | Promtail, Grafana |
| `GF_SECURITY_ADMIN_USER` | `admin` | `admin` | Grafana |
| `GF_SECURITY_ADMIN_PASSWORD` | `admin` | `<production password>` | Grafana |
| `GF_USERS_ALLOW_SIGN_UP` | `false` | `false` | Grafana |
| `GF_SERVER_ROOT_URL` | `http://localhost:3001` | `https://grafana.betterbundle.site` | Grafana |
| `GF_SERVER_DOMAIN` | - | `grafana.betterbundle.site` | Grafana |
| `GF_INSTALL_PLUGINS` | `redis-datasource` | `redis-datasource` | Grafana |
| `GF_LOG_LEVEL` | - | `warn` | Grafana |
| `GRAFANA_LOKI_ENABLED` | `false` | - | Remix app |

### Security

| Variable | Dev Value | Prod Value | Used By |
|----------|-----------|------------|---------|
| `JWT_SECRET` | `dev_jwt_secret_123` | `<production secret>` | Both |
| `ENCRYPTION_KEY` | `dev_encryption_key_123` | `<production key>` | Both |

### Python Worker Specific

| Variable | Dev Value | Description |
|----------|-----------|-------------|
| `PORT` | `8001` | Worker HTTP port |
| `ENVIRONMENT` | `development` | Environment name |
| `DATA_JOB_STREAM` | `betterbundle:data-jobs` | Redis stream name (legacy) |
| `ML_TRAINING_STREAM` | `betterbundle:ml-training` | Redis stream name (legacy) |
| `ANALYSIS_RESULTS_STREAM` | `betterbundle:analysis-results` | Redis stream name (legacy) |
| `USER_NOTIFICATIONS_STREAM` | `betterbundle:user-notifications` | Redis stream name (legacy) |
| `DATA_PROCESSOR_GROUP` | `data-processors` | Redis consumer group (legacy) |
| `ML_API_URL` | `http://localhost:8000` | ML API URL |
| `MAX_INITIAL_DAYS` | `60` | Max days for initial data backfill |
| `MAX_INCREMENTAL_DAYS` | `30` | Max days for incremental sync |
| `FALLBACK_DAYS` | `30` | Fallback period |
| `SHOPIFY_API_RATE_LIMIT` | `40` | Shopify API rate limit |
| `SHOPIFY_API_BATCH_SIZE` | `250` | Shopify API batch size |
| `MAX_RETRIES` | `3` | Max retry count |
| `RETRY_DELAY` | `1.0` | Retry delay seconds |
| `RETRY_BACKOFF` | `2.0` | Retry backoff multiplier |
| `HEALTH_CHECK_TIMEOUT` | `5` | Health check timeout seconds |
| `CORS_ORIGINS` | `["*"]` | CORS allowed origins |
| `LOG_FORMAT` | `console` | Log format |
| `WORKER_ID` | `python-worker-1` | Worker instance ID |
| `WORKER_CONCURRENCY` | `4` | Worker concurrency |

### Remix App Specific

| Variable | Dev Value | Description |
|----------|-----------|-------------|
| `PORT` / `FRONTEND_PORT` | `3000` | Remix app port |
| `BACKEND_URL` | `https://<ngrok URL>` | Backend URL for API calls |
| `PYTHON_WORKER_API_URL` | - (dev) / `http://python-worker:8000` (prod) | Python worker internal URL |

---

## Data Flow Summary

```
Shopify Webhooks
      |
      v
[Remix App] ---> Kafka: "shopify-events" ---> [DataCollectionConsumer]
      |                                              |
      |                                              v
      |                                    Shopify GraphQL API
      |                                              |
      |                                              v
      |                                    raw_* tables (raw data)
      |                                              |
      |                                              v
      |                                    Kafka: "normalization-jobs"
      |                                              |
      |                                              v
      |                                    [NormalizationConsumer]
      |                                         |         |
      |                                         v         v
      |                              normalized tables  Kafka: "feature-computation-jobs"
      |                                   |                    |
      |                                   v                    v
      |                     Kafka: "purchase-attribution"  [FeatureComputationConsumer]
      |                              |                          |
      |                              v                          v
      |                   [PurchaseAttributionConsumer]    Feature tables
      |                              |                          |
      |                              v                          v
      |                   purchase_attributions          Gorse sync (feedback/items/users)
      |                              |
      |                              v
      |                   commission_records
      |                              |
      |                              v
      |                   Kafka: "shopify-usage-events"
      |                              |
      |                              v
      |                   [ShopifyUsageConsumer]
      |                              |
      |                              v
      |                   Shopify Usage API (billing)
      |
      +---> Kafka: "data-collection-jobs" (onboarding)
      +---> Kafka: "access-control" (shop suspension)
      +---> Kafka: "shopify-usage-events" (cap increase, reprocess)
```
