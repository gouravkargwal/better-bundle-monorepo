/*
  Warnings:

  - A unique constraint covering the columns `[shopId,productIds,timeWindow]` on the table `BundleAnalysisResult` will be added. If there are existing duplicate values, this will fail.

*/
-- AlterTable
ALTER TABLE "public"."BundleAnalysisResult" ADD COLUMN     "analysisDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "timeWindow" TEXT NOT NULL DEFAULT '30d';

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_timeWindow_idx" ON "public"."BundleAnalysisResult"("shopId", "timeWindow");

-- CreateIndex
CREATE INDEX "BundleAnalysisResult_shopId_analysisDate_idx" ON "public"."BundleAnalysisResult"("shopId", "analysisDate");

-- CreateIndex
CREATE UNIQUE INDEX "BundleAnalysisResult_shopId_productIds_timeWindow_key" ON "public"."BundleAnalysisResult"("shopId", "productIds", "timeWindow");
