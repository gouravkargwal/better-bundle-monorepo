import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const debugData = await request.json();

    // Log debug information for context detection issues
    console.log("Phoenix Context Debug:", {
      shop: session.shop,
      ...debugData,
      timestamp: new Date().toISOString(),
    });

    // You could also store this in a database table for analysis
    // await prisma.contextDebugLog.create({
    //   data: {
    //     shopId: session.shop,
    //     path: debugData.path,
    //     template: debugData.template,
    //     pageType: debugData.pageType,
    //     theme: debugData.theme,
    //     userAgent: debugData.userAgent,
    //     timestamp: new Date(debugData.timestamp)
    //   }
    // });

    return json({ success: true });
  } catch (error) {
    console.error("Debug endpoint error:", error);
    return json(
      { success: false, error: "Debug logging failed" },
      { status: 500 },
    );
  }
};
