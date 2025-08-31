import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Define required scopes (matching the server-side configuration)
const REQUIRED_SCOPES = [
  "write_products",
  "read_products", 
  "read_orders",
  "write_orders"
];

function getCorrectScopesString() {
  return REQUIRED_SCOPES.join(',');
}

function hasRequiredScopes(sessionScope) {
  if (!sessionScope) return false;
  const sessionScopes = sessionScope.split(',').map(s => s.trim());
  return REQUIRED_SCOPES.every(scope => sessionScopes.includes(scope));
}

async function fixScopesAfterAuth(shopDomain) {
  console.log(`🔧 Fixing scopes after authentication for shop: ${shopDomain}`);

  try {
    // Wait a moment for the session to be created
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Get the session
    const session = await prisma.session.findUnique({
      where: { id: `offline_${shopDomain}` }
    });

    if (!session) {
      console.log(`❌ No session found for ${shopDomain}`);
      return false;
    }

    console.log(`📋 Current session scopes: ${session.scope}`);
    console.log(`📋 Required scopes: ${getCorrectScopesString()}`);

    if (hasRequiredScopes(session.scope)) {
      console.log(`✅ Session already has correct scopes`);
      return true;
    }

    console.log(`🔄 Session has incorrect scopes, fixing...`);

    // Update the session with correct scopes
    const updatedSession = await prisma.session.update({
      where: { id: `offline_${shopDomain}` },
      data: { scope: getCorrectScopesString() }
    });

    console.log(`✅ Session scopes updated successfully`);
    console.log(`📋 New session scopes: ${updatedSession.scope}`);

    // Also ensure shop record exists with correct access token
    const shop = await prisma.shop.findUnique({
      where: { shopDomain }
    });

    if (shop) {
      console.log(`🏪 Updating shop record access token`);
      await prisma.shop.update({
        where: { shopDomain },
        data: { accessToken: session.accessToken }
      });
      console.log(`✅ Shop record updated`);
    } else {
      console.log(`🏪 Creating new shop record`);
      await prisma.shop.create({
        data: {
          shopId: shopDomain,
          shopDomain: shopDomain,
          accessToken: session.accessToken,
          planType: "Free",
          isActive: true
        }
      });
      console.log(`✅ Shop record created`);
    }

    return true;

  } catch (error) {
    console.error(`❌ Error fixing scopes:`, error);
    return false;
  } finally {
    await prisma.$disconnect();
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('Usage: node scripts/fix-scopes-after-auth.js <shop-domain>');
  console.log('Example: node scripts/fix-scopes-after-auth.js vnsaid.myshopify.com');
  process.exit(1);
}

fixScopesAfterAuth(shopDomain);
