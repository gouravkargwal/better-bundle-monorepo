-- Clean up duplicate bundle analysis results
-- Keep only the most recent result for each unique combination

DELETE FROM "BundleAnalysisResult" 
WHERE id NOT IN (
  SELECT DISTINCT ON (shop_id, product_ids, time_window) id
  FROM "BundleAnalysisResult"
  ORDER BY shop_id, product_ids, time_window, "lastUpdated" DESC
);

-- Add the unique constraint after cleaning duplicates
ALTER TABLE "BundleAnalysisResult" 
ADD CONSTRAINT "BundleAnalysisResult_shopId_productIds_timeWindow_key" 
UNIQUE (shop_id, product_ids, time_window);
