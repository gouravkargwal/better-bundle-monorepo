import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Define required scopes (matching the server-side SessionScopeManager)
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

async function updateSessionScopes(shopDomain) {
  console.log(`🔄 Updating session scopes for shop: ${shopDomain}`);

  try {
    const correctScopes = getCorrectScopesString();
    console.log(`📋 Correct scopes: ${correctScopes}`);

    // Find the session
    const session = await prisma.session.findUnique({
      where: { id: `offline_${shopDomain}` }
    });

    if (!session) {
      console.log(`⚠️ No session found for ${shopDomain}`);
      return false;
    }

    console.log(`📋 Current session scopes: ${session.scope}`);
    console.log(`📋 Current session ID: ${session.id}`);

    if (hasRequiredScopes(session.scope)) {
      console.log(`✅ Session already has correct scopes`);
      return true;
    }

    // Update the session with correct scopes
    const updatedSession = await prisma.session.update({
      where: { id: `offline_${shopDomain}` },
      data: { scope: correctScopes }
    });

    console.log(`✅ Session updated successfully`);
    console.log(`📋 New session scopes: ${updatedSession.scope}`);

    // Also update the shop record if it exists
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
    console.error(`❌ Error updating session:`, error);
    return false;
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.error('❌ Please provide a shop domain as an argument');
  console.log('Usage: node update-session-scopes.js <shop-domain>');
  console.log('Example: node update-session-scopes.js mystore.myshopify.com');
  process.exit(1);
}

// Run the update
updateSessionScopes(shopDomain)
  .then((success) => {
    if (success) {
      console.log(`✅ Session scopes update completed successfully for ${shopDomain}`);
    } else {
      console.log(`❌ Session scopes update failed for ${shopDomain}`);
    }
  })
  .catch((error) => {
    console.error('❌ Unexpected error:', error);
  })
  .finally(() => {
    prisma.$disconnect();
  });
