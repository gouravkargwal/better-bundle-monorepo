# Trigger Analysis and Webhooks - New Flow Guide

## Overview

This guide explains how the new API client structure integrates with trigger analysis and webhooks to provide a unified data collection flow.

## Architecture

### 1. **Analysis Triggers** (Full Data Collection)

- **Triggered by**: Onboarding, manual analysis requests
- **Data Collection**: All data types (products, orders, customers, collections)
- **Mode**: Historical (full sync) or Incremental
- **Flow**: Frontend → Analysis Service → Kafka → Data Collection Consumer → New API Client

### 2. **Webhook Triggers** (Specific Item Collection)

- **Triggered by**: Shopify webhooks (product updates, order payments, etc.)
- **Data Collection**: Specific items by ID
- **Mode**: Incremental only
- **Flow**: Shopify → Webhook Route → Kafka → Webhook Consumer → Data Collection Consumer → New API Client

## New Flow Implementation

### **Step 1: Analysis Service Updates**

#### **Full Analysis Trigger**

```typescript
// better-bundle/app/services/analysis.service.ts
export const triggerFullAnalysis = async (shopDomain: string) => {
  // ... existing code ...

  // NEW: Create collection payload for full analysis
  const collectionPayload = {
    data_types: ["products", "orders", "customers", "collections"],
  };

  const jobData = {
    event_type: "data_collection",
    job_id: jobId,
    shop_id: shop.id,
    mode: "historical",
    collection_payload: collectionPayload, // NEW: specify what data to collect
    trigger_source: "analysis", // NEW: indicate this is triggered by analysis
    timestamp: new Date().toISOString(),
  };

  // ... rest of the code ...
};
```

#### **Specific Data Collection Trigger**

```typescript
// better-bundle/app/services/analysis.service.new.ts
export const triggerSpecificDataCollection = async (
  shopDomain: string,
  dataTypes: string[],
  mode: "incremental" | "historical" = "incremental"
) => {
  const collectionPayload = {
    data_types: dataTypes,
  };

  // ... rest of the implementation ...
};
```

### **Step 2: Webhook Consumer**

#### **New Webhook Consumer**

```python
# python-worker/app/consumers/kafka/webhook_consumer.py
class WebhookKafkaConsumer:
    """Kafka consumer for webhook events that triggers specific data collection"""

    async def _process_webhook_event(self, event_type: str, shop_id: str, shopify_id: str, event: Dict[str, Any]) -> bool:
        # Map event types to data types and collection payloads
        collection_payload = self._create_collection_payload(event_type, shopify_id)

        # Create data collection job
        data_collection_event = {
            "event_type": "data_collection",
            "job_id": f"webhook_{event_type}_{shopify_id}_{timestamp}",
            "shop_id": shop_id,
            "mode": "incremental",
            "collection_payload": collection_payload,
            "trigger_source": "webhook",
            "trigger_event": event_type,
            "shopify_id": shopify_id,
        }

        # Publish data collection job
        await self.event_publisher.publish_data_collection_job(data_collection_event)
```

#### **Event Type Mapping**

```python
def _create_collection_payload(self, event_type: str, shopify_id: str) -> Dict[str, Any]:
    event_mapping = {
        # Product events
        "product_created": {"data_type": "products", "specific_ids": [shopify_id]},
        "product_updated": {"data_type": "products", "specific_ids": [shopify_id]},
        "product_deleted": {"data_type": "products", "specific_ids": [shopify_id]},

        # Collection events
        "collection_created": {"data_type": "collections", "specific_ids": [shopify_id]},
        "collection_updated": {"data_type": "collections", "specific_ids": [shopify_id]},
        "collection_deleted": {"data_type": "collections", "specific_ids": [shopify_id]},

        # Order events
        "order_paid": {"data_type": "orders", "specific_ids": [shopify_id]},
        "order_created": {"data_type": "orders", "specific_ids": [shopify_id]},
        "order_updated": {"data_type": "orders", "specific_ids": [shopify_id]},
        "order_cancelled": {"data_type": "orders", "specific_ids": [shopify_id]},

        # Customer events
        "customer_created": {"data_type": "customers", "specific_ids": [shopify_id]},
        "customer_updated": {"data_type": "customers", "specific_ids": [shopify_id]},
    }

    return event_mapping.get(event_type)
```

### **Step 3: Data Collection Service Updates**

#### **Updated Data Collection Service**

```python
# python-worker/app/domains/shopify/services/data_collection.py
async def _collect_single_item_by_id(self, data_type: str, shop_domain: str, item_id: str) -> Dict[str, Any]:
    """Collect a single item by ID using new API client methods with full data traversal"""
    try:
        if data_type == "products":
            # Use the new get_products method with product_ids parameter
            result = await self.api_client.get_products(
                shop_domain=shop_domain,
                product_ids=[item_id]
            )
            # Extract the product from the edges format
            edges = result.get("edges", [])
            if edges:
                return edges[0]["node"]
            return None
        elif data_type == "collections":
            # Use the new get_collections method with collection_ids parameter
            result = await self.api_client.get_collections(
                shop_domain=shop_domain,
                collection_ids=[item_id]
            )
            # Extract the collection from the edges format
            edges = result.get("edges", [])
            if edges:
                return edges[0]["node"]
            return None
        # ... similar for orders and customers
```

### **Step 4: API Client Integration**

#### **New API Client Structure**

```python
# python-worker/app/domains/shopify/services/api_client_new.py
class ShopifyAPIClient(IShopifyAPIClient):
    """Main Shopify API client that delegates to specialized clients"""

    def __init__(self):
        # Initialize specialized clients
        self.product_client = ProductAPIClient()
        self.collection_client = CollectionAPIClient()
        self.order_client = OrderAPIClient()
        self.customer_client = CustomerAPIClient()

    async def get_products(self, shop_domain: str, product_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get products - supports both pagination and specific IDs"""
        return await self.product_client.get_products(shop_domain, product_ids=product_ids)

    async def get_collections(self, shop_domain: str, collection_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get collections - supports both pagination and specific IDs"""
        return await self.collection_client.get_collections(shop_domain, collection_ids=collection_ids)
```

## Event Flow Examples

### **Example 1: Analysis Trigger (Full Collection)**

```
1. User completes onboarding
2. Frontend calls triggerFullAnalysis(shopDomain)
3. Analysis service creates job with collection_payload: {data_types: ["products", "orders", "customers", "collections"]}
4. Kafka publishes to "data-collection-jobs" topic
5. DataCollectionKafkaConsumer receives event
6. Data collection service calls collect_all_data() with collection_payload
7. New API client collects all data types with full data traversal
```

### **Example 2: Webhook Trigger (Specific Item)**

```
1. Shopify product updated
2. Webhook route receives product_updated event
3. Kafka publishes to "shopify-events" topic
4. WebhookKafkaConsumer receives event
5. Webhook consumer creates data collection job with collection_payload: {data_type: "products", specific_ids: ["123"]}
6. Kafka publishes to "data-collection-jobs" topic
7. DataCollectionKafkaConsumer receives event
8. Data collection service calls collect_all_data() with specific collection_payload
9. New API client collects specific product with full data traversal (variants, images, metafields)
```

## Benefits of New Flow

### **1. Unified Data Collection**

- Single `collect_all_data()` method handles both analysis and webhook triggers
- Collection payload determines what data to collect
- No duplicate logic or separate flows

### **2. Full Data Traversal**

- All API clients support complete data fetching
- Products: variants, images, metafields
- Collections: products within collections
- Orders: line items within orders
- Customers: addresses within customers

### **3. Efficient Webhook Processing**

- Only collect specific items that changed
- Reuse existing data traversal logic
- Maintain data consistency

### **4. Maintainable Code**

- Specialized API clients for each data type
- Common functionality in base client
- Easy to extend and test

## Migration Steps

### **1. Update Imports**

```python
# Old
from app.domains.shopify.services.api_client import ShopifyAPIClient

# New
from app.domains.shopify.services.api_client_new import ShopifyAPIClient
```

### **2. Deploy New Consumers**

```python
# Start webhook consumer
webhook_consumer = WebhookKafkaConsumer()
await webhook_consumer.start_consuming()

# Start data collection consumer (updated)
data_collection_consumer = DataCollectionKafkaConsumer(shopify_service)
await data_collection_consumer.start_consuming()
```

### **3. Test Both Flows**

- Test analysis trigger (full collection)
- Test webhook trigger (specific items)
- Verify data consistency and completeness

## Configuration

### **Kafka Topics**

- `shopify-events`: Webhook events from Shopify
- `data-collection-jobs`: Data collection jobs (analysis + webhook triggered)

### **Consumer Groups**

- `webhook-processors`: Process webhook events
- `data-collection-processors`: Process data collection jobs

### **Event Types**

- Analysis: `data_collection` with `trigger_source: "analysis"`
- Webhook: `data_collection` with `trigger_source: "webhook"`

This new flow provides a unified, efficient, and maintainable approach to data collection that handles both bulk analysis and real-time webhook updates while maintaining full data traversal capabilities.
