import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

// Simple in-memory rate limiting (in production, use Redis or similar)
const requestCounts = new Map<string, { count: number; resetTime: number }>();
const RATE_LIMIT_WINDOW = 60000; // 1 minute
const MAX_REQUESTS_PER_WINDOW = 10; // Max 10 requests per minute

function checkRateLimit(identifier: string): boolean {
  const now = Date.now();
  const record = requestCounts.get(identifier);
  
  if (!record || now > record.resetTime) {
    // Reset or create new record
    requestCounts.set(identifier, {
      count: 1,
      resetTime: now + RATE_LIMIT_WINDOW
    });
    return true;
  }
  
  if (record.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }
  
  record.count++;
  return true;
}

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    console.log("🔐 Starting authentication for status check");
    
    // Add request debugging
    const url = new URL(request.url);
    console.log("🔍 Request details:", {
      method: request.method,
      url: url.pathname,
      searchParams: Object.fromEntries(url.searchParams.entries()),
      headers: Object.fromEntries(request.headers.entries())
    });
    
    const { session } = await authenticate.admin(request);
    
    console.log("🔐 Authentication result:", {
      hasSession: !!session,
      shop: session?.shop,
      hasAccessToken: !!session?.accessToken,
      sessionId: session?.id,
      expires: session?.expires
    });
    
    if (!session?.shop) {
      console.error("❌ No shop in session - authentication failed");
      return json(
        {
          success: false,
          error: "Authentication failed - no shop in session",
          debug: {
            hasSession: !!session,
            sessionId: session?.id,
            expires: session?.expires
          }
        },
        { status: 401 }
      );
    }
    
    const shopId = session.shop;
    
    // Check rate limit
    if (!checkRateLimit(shopId)) {
      console.warn(`⏳ Rate limit exceeded for shop: ${shopId}`);
      return json(
        {
          success: false,
          error: "Rate limit exceeded. Please wait before making more requests.",
        },
        { status: 429 }
      );
    }
    
    const jobId = url.searchParams.get("jobId");

    console.log(`🔍 Looking up shop: ${shopId}`);

    // Get shop from database
    const shop = await prisma.shop.findUnique({
      where: { shopDomain: shopId },
      select: { id: true },
    });

    if (!shop) {
      console.error(`❌ Shop not found in database: ${shopId}`);
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
        console.log(`❌ Job not found: ${jobId}`);
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
    console.error("❌ Error getting analysis status:", error);
    
    // Check if it's an authentication error
    if (error instanceof Error) {
      if (error.message.includes("authentication") || error.message.includes("session")) {
        console.error("🔐 Authentication error detected:", error.message);
        return json(
          {
            success: false,
            error: "Authentication failed",
            debug: {
              errorMessage: error.message,
              errorStack: error.stack
            }
          },
          { status: 401 },
        );
      }
      
      if (error.message.includes("rate limit") || error.message.includes("429")) {
        console.error("⏳ Rate limit error detected:", error.message);
        return json(
          {
            success: false,
            error: "Rate limit exceeded",
          },
          { status: 429 },
        );
      }
    }
    
    return json(
      {
        success: false,
        error: "Failed to get analysis status",
        debug: {
          errorMessage: error instanceof Error ? error.message : String(error)
        }
      },
      { status: 500 },
    );
  }
};
