-- AlterTable
ALTER TABLE "public"."BundleAnalysisResult" ADD COLUMN     "discount" DOUBLE PRECISION NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE "public"."WidgetConfiguration" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "isEnabled" BOOLEAN NOT NULL DEFAULT false,
    "theme" TEXT NOT NULL DEFAULT 'auto',
    "position" TEXT NOT NULL DEFAULT 'product_page',
    "title" TEXT NOT NULL DEFAULT 'Frequently Bought Together',
    "showImages" BOOLEAN NOT NULL DEFAULT true,
    "showIndividualButtons" BOOLEAN NOT NULL DEFAULT true,
    "showBundleTotal" BOOLEAN NOT NULL DEFAULT true,
    "globalDiscount" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "WidgetConfiguration_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "WidgetConfiguration_shopId_key" ON "public"."WidgetConfiguration"("shopId");

-- AddForeignKey
ALTER TABLE "public"."WidgetConfiguration" ADD CONSTRAINT "WidgetConfiguration_shopId_fkey" FOREIGN KEY ("shopId") REFERENCES "public"."Shop"("id") ON DELETE CASCADE ON UPDATE CASCADE;
