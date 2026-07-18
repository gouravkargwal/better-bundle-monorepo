import { type ActionFunctionArgs, json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import logger from "../utils/logger";

/**
 * POST /api/onboarding/retrigger-analysis
 *
 * Re-publishes the data collection job to Kafka so the Python worker
 * restarts historical analysis of products, orders, customers, etc.
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  const shopRecord = await prisma.shops.findUnique({
    where: { shop_domain: session.shop },
    select: { id: true, access_token: true },
  });

  if (!shopRecord) {
    return json({ success: false, error: "Shop not found" }, { status: 404 });
  }

  try {
    const jobId = `analysis_${session.shop}_${Date.now()}`;
    const jobData = {
      event_type: "data_collection",
      job_id: jobId,
      shop_id: shopRecord.id,
      job_type: "data_collection",
      mode: "historical",
      collection_payload: {
        data_types: ["products", "orders", "customers", "collections"],
      },
      trigger_source: "retry",
      timestamp: new Date().toISOString(),
    };

    const producer = await KafkaProducerService.getInstance();
    await producer.publishDataJobEvent(jobData);

    return json({ success: true });
  } catch (error: any) {
    logger.error({ error }, "Failed to retrigger analysis");
    return json(
      {
        success: false,
        error: error.message || "Failed to retrigger analysis",
      },
      { status: 500 },
    );
  }
};
