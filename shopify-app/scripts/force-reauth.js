import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function forceReauth(shopDomain) {
  console.log(`🔄 Forcing re-authentication for shop: ${shopDomain}`);

  try {
    // Delete the old session
    const deletedSessions = await prisma.session.deleteMany({
      where: { shop: shopDomain }
    });
    console.log(`🗑️ Deleted ${deletedSessions.count} old sessions`);

    // Delete any existing shop record
    const deletedShops = await prisma.shop.deleteMany({
      where: { shopDomain }
    });
    console.log(`🗑️ Deleted ${deletedShops.count} old shop records`);

    console.log(`✅ Cleanup completed. Now you need to:`);
    console.log(`1. Go to your Shopify admin: https://${shopDomain}/admin`);
    console.log(`2. Navigate to Apps > BetterBundle`);
    console.log(`3. The app will redirect you to re-authenticate`);
    console.log(`4. This will create a fresh session with the correct scopes`);

  } catch (error) {
    console.error(`❌ Error during cleanup:`, error);
  } finally {
    await prisma.$disconnect();
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('Usage: node scripts/force-reauth.js <shop-domain>');
  console.log('Example: node scripts/force-reauth.js vnsaid.myshopify.com');
  process.exit(1);
}

forceReauth(shopDomain);
