import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { AnalysisPipelineService } from "../services/analysis-pipeline.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  if (request.method !== "POST") {
    return json({ error: "Method not allowed" }, { status: 405 });
  }

  try {
    const shopDomain = session.shop;
    const accessToken = (session as any).accessToken;

    if (!shopDomain || !accessToken) {
      return json(
        { error: "Missing shop domain or access token" },
        { status: 400 },
      );
    }

    // Trigger the analysis pipeline
    const result = await AnalysisPipelineService.triggerInitialAnalysis({
      shopDomain,
      accessToken,
    });

    if (!result) {
      return json(
        {
          error: "Failed to trigger analysis pipeline",
          success: false,
        },
        { status: 500 },
      );
    }

    return json({
      success: true,
      message: "Analysis pipeline triggered successfully",
      jobId: result.job_id,
      eventId: result.event_id,
    });
  } catch (error) {
    console.error("Error triggering analysis pipeline:", error);
    return json(
      {
        error: "Internal server error",
        success: false,
      },
      { status: 500 },
    );
  }
};

export const loader = async ({ request }: ActionFunctionArgs) => {
  return json({ error: "GET method not allowed" }, { status: 405 });
};
