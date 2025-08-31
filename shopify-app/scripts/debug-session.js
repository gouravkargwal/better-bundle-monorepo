import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function debugSession(shopDomain) {
  console.log(`🔍 Debugging session for shop: ${shopDomain}`);

  try {
    // Check sessions
    const sessions = await prisma.session.findMany({
      where: { shop: shopDomain }
    });
    console.log(`📋 Sessions found: ${sessions.length}`);

    // Separate online and offline sessions
    const onlineSessions = sessions.filter(s => s.isOnline);
    const offlineSessions = sessions.filter(s => !s.isOnline);

    console.log(`📋 Online sessions: ${onlineSessions.length}`);
    onlineSessions.forEach((session, index) => {
      console.log(`  Online Session ${index + 1}:`, {
        id: session.id,
        shop: session.shop,
        isOnline: session.isOnline,
        scope: session.scope,
        expires: session.expires,
        accessToken: session.accessToken ? `${session.accessToken.substring(0, 20)}...` : 'null',
        userId: session.userId,
        email: session.email
      });
    });

    console.log(`📋 Offline sessions: ${offlineSessions.length}`);
    offlineSessions.forEach((session, index) => {
      console.log(`  Offline Session ${index + 1}:`, {
        id: session.id,
        shop: session.shop,
        isOnline: session.isOnline,
        scope: session.scope,
        expires: session.expires,
        accessToken: session.accessToken ? `${session.accessToken.substring(0, 20)}...` : 'null',
        userId: session.userId,
        email: session.email
      });
    });

    // Check shop record
    const shop = await prisma.shop.findUnique({
      where: { shopDomain }
    });

    if (shop) {
      console.log(`🏪 Shop record found:`, {
        id: shop.id,
        shopId: shop.shopId,
        shopDomain: shop.shopDomain,
        accessToken: shop.accessToken ? `${shop.accessToken.substring(0, 20)}...` : 'null',
        planType: shop.planType,
        isActive: shop.isActive,
        createdAt: shop.createdAt,
        updatedAt: shop.updatedAt
      });
    } else {
      console.log(`⚠️ No shop record found for ${shopDomain}`);
    }

    // Check analysis jobs
    const jobs = await prisma.analysisJob.findMany({
      where: { shopId: shop?.id },
      orderBy: { createdAt: 'desc' },
      take: 5
    });
    console.log(`📊 Recent analysis jobs: ${jobs.length}`);
    jobs.forEach((job, index) => {
      console.log(`  Job ${index + 1}:`, {
        id: job.id,
        jobId: job.jobId,
        status: job.status,
        progress: job.progress,
        error: job.error,
        createdAt: job.createdAt,
        completedAt: job.completedAt
      });
    });

  } catch (error) {
    console.error(`❌ Error during debug:`, error);
  } finally {
    await prisma.$disconnect();
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('Usage: node scripts/debug-session.js <shop-domain>');
  console.log('Example: node scripts/debug-session.js vnsaid.myshopify.com');
  process.exit(1);
}

debugSession(shopDomain);
