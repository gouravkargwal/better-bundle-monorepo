export interface CustomerLinkedData {
  customerId: string;
  clientId: string;
  linkedAt?: string;
}

// Base event type
export interface BaseEvent {
  id: string;
  timestamp: string;
  customerId?: string;
  context?: any;
  clientId?: string;
  seq?: number;
  type?: string;
}

export interface CustomerLinkedEvent extends BaseEvent {
  name: "customer_linked";
  data: CustomerLinkedData;
}

// Configuration types
export interface AtlasConfig {
  backendUrl: string;
  shopDomain: string | null; // Shop domain from Shopify context
}

// API response types
export interface ApiResponse {
  success: boolean;
  eventId?: string;
  error?: string;
}
