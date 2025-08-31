import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    
    if (!session?.shop) {
      console.error("❌ No shop in session");
      return json(
        {
          success: false,
          error: "Authentication failed - no shop in session",
        },
        { status: 401 }
      );
    }
    
    const shopId = session.shop;
    const url = new URL(request.url);
    const jobId = url.searchParams.get("jobId");

    // Get shop from database
    const shop = await prisma.shop.findUnique({
      where: { shopDomain: shopId },
      select: { id: true },
    });

    if (!shop) {
      return json(
        {
          success: false,
          error: "Shop not found",
        },
        { status: 404 },
      );
    }

    if (jobId) {
      // Get specific job status
      const jobStatus = await prisma.analysisJob.findFirst({
        where: {
          jobId,
          shopId: shop.id,
        },
        select: {
          id: true,
          jobId: true,
          status: true,
          progress: true,
          error: true,
          result: true,
          createdAt: true,
          startedAt: true,
          completedAt: true,
        },
      });

      console.log(
        `🔍 Job status lookup for jobId: ${jobId}, shopId: ${shop.id}`,
      );
      console.log(`📊 Found job status:`, jobStatus);

      if (!jobStatus) {
        return json(
          {
            success: false,
            error: "Job not found",
          },
          { status: 404 },
        );
      }

      return json({
        success: true,
        job: jobStatus,
      });
    } else {
      // Get all jobs for the shop
      const jobs = await prisma.analysisJob.findMany({
        where: { shopId: shop.id },
        orderBy: { createdAt: "desc" },
        take: 10,
        select: {
          id: true,
          jobId: true,
          status: true,
          progress: true,
          error: true,
          result: true,
          createdAt: true,
          startedAt: true,
          completedAt: true,
        },
      });

      return json({
        success: true,
        jobs: jobs,
        totalJobs: jobs.length,
      });
    }
  } catch (error) {
    console.error("Error getting analysis status:", error);
    
    // Check if it's an authentication error
    if (error instanceof Error && error.message.includes("authentication")) {
      return json(
        {
          success: false,
          error: "Authentication failed",
        },
        { status: 401 },
      );
    }
    
    return json(
      {
        success: false,
        error: "Failed to get analysis status",
      },
      { status: 500 },
    );
  }
};
