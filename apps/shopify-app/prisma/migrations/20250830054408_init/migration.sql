-- CreateTable
CREATE TABLE "public"."Session" (
    "id" TEXT NOT NULL,
    "shop" TEXT NOT NULL,
    "state" TEXT NOT NULL,
    "isOnline" BOOLEAN NOT NULL DEFAULT false,
    "scope" TEXT,
    "expires" TIMESTAMP(3),
    "accessToken" TEXT NOT NULL,
    "userId" BIGINT,
    "firstName" TEXT,
    "lastName" TEXT,
    "email" TEXT,
    "accountOwner" BOOLEAN NOT NULL DEFAULT false,
    "locale" TEXT,
    "collaborator" BOOLEAN DEFAULT false,
    "emailVerified" BOOLEAN DEFAULT false,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."Shop" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "shopDomain" TEXT NOT NULL,
    "accessToken" TEXT NOT NULL,
    "planType" TEXT NOT NULL DEFAULT 'Free',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "lastAnalysisAt" TIMESTAMP(3),

    CONSTRAINT "Shop_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."OrderData" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "customerId" TEXT,
    "totalAmount" DOUBLE PRECISION NOT NULL,
    "orderDate" TIMESTAMP(3) NOT NULL,
    "lineItems" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "OrderData_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."ProductData" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "productId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "handle" TEXT NOT NULL,
    "category" TEXT,
    "price" DOUBLE PRECISION NOT NULL,
    "inventory" INTEGER,
    "tags" JSONB,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ProductData_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."BundleAnalysisResult" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "productIds" TEXT[],
    "bundleSize" INTEGER NOT NULL,
    "coPurchaseCount" INTEGER NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "lift" DOUBLE PRECISION NOT NULL,
    "support" DOUBLE PRECISION NOT NULL,
    "revenue" DOUBLE PRECISION NOT NULL,
    "avgOrderValue" DOUBLE PRECISION NOT NULL,
    "priceRange" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "lastUpdated" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "BundleAnalysisResult_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."TrackedSale" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "shopifyOrderId" TEXT NOT NULL,
    "revenueGenerated" DOUBLE PRECISION NOT NULL,
    "commissionOwed" DOUBLE PRECISION NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "billingPeriod" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "TrackedSale_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."WidgetEvent" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "bundleId" TEXT,
    "action" TEXT NOT NULL,
    "productIds" TEXT[],
    "timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "WidgetEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Shop_shopId_key" ON "public"."Shop"("shopId");

-- CreateIndex
CREATE UNIQUE INDEX "Shop_shopDomain_key" ON "public"."Shop"("shopDomain");

-- CreateIndex
CREATE INDEX "OrderData_shopId_orderDate_idx" ON "public"."OrderData"("shopId", "orderDate");

-- CreateIndex
CREATE INDEX "OrderData_shopId_customerId_idx" ON "public"."OrderData"("shopId", "customerId");

-- CreateIndex
CREATE UNIQUE INDEX "OrderData_shopId_orderId_key" ON "public"."OrderData"("shopId", "orderId");

-- CreateIndex
CREATE INDEX "ProductData_shopId_category_idx" ON "public"."ProductData"("shopId", "category");

-- CreateIndex
CREATE INDEX "ProductData_shopId_price_idx" ON "public"."ProductData"("shopId", "price");

-- CreateIndex
CREATE INDEX "ProductData_shopId_isActive_idx" ON "public"."ProductData"("shopId", "isActive");

-- CreateIndex
CREATE UNIQUE INDEX "ProductData_shopId_productId_key" ON "public"."ProductData"("shopId", "productId");

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_confidence_idx" ON "public"."BundleAnalysisResult"("shopId", "confidence");

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_lift_idx" ON "public"."BundleAnalysisResult"("shopId", "lift");

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_revenue_idx" ON "public"."BundleAnalysisResult"("shopId", "revenue");

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_isActive_idx" ON "public"."BundleAnalysisResult"("shopId", "isActive");

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_bundleSize_idx" ON "public"."BundleAnalysisResult"("shopId", "bundleSize");

-- CreateIndex
CREATE INDEX "TrackedSale_shopId_billingPeriod_idx" ON "public"."TrackedSale"("shopId", "billingPeriod");

-- CreateIndex
CREATE INDEX "TrackedSale_shopId_status_idx" ON "public"."TrackedSale"("shopId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "TrackedSale_shopId_shopifyOrderId_key" ON "public"."TrackedSale"("shopId", "shopifyOrderId");

-- CreateIndex
CREATE INDEX "WidgetEvent_shopId_sessionId_idx" ON "public"."WidgetEvent"("shopId", "sessionId");

-- CreateIndex
CREATE INDEX "WidgetEvent_shopId_action_idx" ON "public"."WidgetEvent"("shopId", "action");

-- CreateIndex
CREATE INDEX "WidgetEvent_shopId_timestamp_idx" ON "public"."WidgetEvent"("shopId", "timestamp");

-- AddForeignKey
ALTER TABLE "public"."OrderData" ADD CONSTRAINT "OrderData_shopId_fkey" FOREIGN KEY ("shopId") REFERENCES "public"."Shop"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."ProductData" ADD CONSTRAINT "ProductData_shopId_fkey" FOREIGN KEY ("shopId") REFERENCES "public"."Shop"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."BundleAnalysisResult" ADD CONSTRAINT "BundleAnalysisResult_shopId_fkey" FOREIGN KEY ("shopId") REFERENCES "public"."Shop"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."TrackedSale" ADD CONSTRAINT "TrackedSale_shopId_fkey" FOREIGN KEY ("shopId") REFERENCES "public"."Shop"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "public"."WidgetEvent" ADD CONSTRAINT "WidgetEvent_shopId_fkey" FOREIGN KEY ("shopId") REFERENCES "public"."Shop"("id") ON DELETE CASCADE ON UPDATE CASCADE;
