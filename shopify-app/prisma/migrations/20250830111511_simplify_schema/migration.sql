/*
  Warnings:

  - You are about to drop the column `lastUpdated` on the `BundleAnalysisResult` table. All the data in the column will be lost.
  - You are about to drop the column `priceRange` on the `BundleAnalysisResult` table. All the data in the column will be lost.
  - You are about to drop the column `timeWindow` on the `BundleAnalysisResult` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[shopId,productIds]` on the table `BundleAnalysisResult` will be added. If there are existing duplicate values, this will fail.

*/
-- DropIndex
DROP INDEX "public"."BundleAnalysisResult_shopId_productIds_timeWindow_key";

-- DropIndex
DROP INDEX "public"."BundleAnalysisResult_shopId_timeWindow_idx";

-- AlterTable
ALTER TABLE "public"."BundleAnalysisResult" DROP COLUMN "lastUpdated",
DROP COLUMN "priceRange",
DROP COLUMN "timeWindow";

-- CreateIndex
CREATE UNIQUE INDEX "BundleAnalysisResult_shopId_productIds_key" ON "public"."BundleAnalysisResult"("shopId", "productIds");
