import type { ActionFunctionArgs } from "@remix-run/node";
import { prisma } from "../core/database/prisma.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { jobId, status, progress, error } = await request.json();

    // Update job status in database
    await prisma.analysisJob.update({
      where: { jobId },
      data: {
        status,
        progress,
        error: error || null,
        completedAt: status === "completed" || status === "failed" ? new Date() : null,
      },
    });

    return Response.json({ success: true });
  } catch (error) {
    console.error("Error updating job status:", error);
    return Response.json(
      { success: false, error: "Failed to update job status" },
      { status: 500 }
    );
  }
};
