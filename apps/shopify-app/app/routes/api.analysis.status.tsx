import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;
    const url = new URL(request.url);
    const jobId = url.searchParams.get("jobId");

    // Get shop from database
    const shop = await prisma.shop.findUnique({
      where: { shopId },
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

    return json(
      {
        success: false,
        error: "Failed to get analysis status",
      },
      { status: 500 },
    );
  }
};
