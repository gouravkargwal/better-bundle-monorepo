import { getRedisClient } from "./redis.service";

export const triggerFullAnalysis = async (shopDomain: string) => {
  try {
    const redis = await getRedisClient();

    // Create a deterministic job ID to prevent duplicates
    const jobId = `analysis_${shopDomain}_${Date.now()}`;

    // Check if this exact job already exists (deduplication)
    const existingJobs = await redis.xRange(
      "betterbundle:data-collection-jobs",
      "-",
      "+",
      { COUNT: 100 },
    );

    const duplicateJob = existingJobs.find(
      (job) =>
        job.message.job_id === jobId ||
        (job.message.shop_domain === shopDomain &&
          job.message.trigger_source === "manual_analysis" &&
          Date.now() - parseInt(job.message.timestamp) < 300000), // 5 minutes
    );

    if (duplicateJob) {
      console.log(`🔄 Skipping duplicate analysis job for ${shopDomain}`);
      return { success: true, messageId: duplicateJob.id, skipped: true };
    }

    const eventData = {
      job_id: jobId,
      shop_domain: shopDomain,
      job_type: "data_collection",
      data_types: JSON.stringify([
        "products",
        "orders",
        "customers",
        "collections",
      ]),
      trigger_source: "manual_analysis",
      timestamp: new Date().toISOString(),
      priority: "high",
    };

    const messageId = await redis.xAdd(
      "betterbundle:data-collection-jobs",
      "*",
      eventData,
    );
    console.log(`✅ Data collection event published: ${messageId}`);
    return { success: true, messageId };
  } catch (error: any) {
    console.error("❌ Failed to publish data collection event:", error);
    throw new Error(`Failed to trigger analysis: ${error.message}`);
  }
};
