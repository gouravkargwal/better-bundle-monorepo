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

async function forceScopeUpdate(shopDomain) {
  console.log(`🔧 Forcing scope update for shop: ${shopDomain}`);

  try {
    // Get the current session
    const session = await prisma.session.findUnique({
      where: { id: `offline_${shopDomain}` }
    });

    if (!session) {
      console.log(`❌ No session found for ${shopDomain}`);
      return false;
    }

    console.log(`📋 Current session scopes: ${session.scope}`);
    console.log(`📋 Required scopes: ${getCorrectScopesString()}`);

    // Check if we have the correct scopes
    const currentScopes = session.scope?.split(',').map(s => s.trim()) || [];
    const missingScopes = REQUIRED_SCOPES.filter(scope => !currentScopes.includes(scope));

    if (missingScopes.length === 0) {
      console.log(`✅ Session already has all required scopes`);
      return true;
    }

    console.log(`❌ Missing scopes: ${missingScopes.join(', ')}`);
    console.log(`\n🔧 To fix this issue:`);
    console.log(`1. Go to your Shopify admin: https://${shopDomain}/admin`);
    console.log(`2. Navigate to Apps > BetterBundle`);
    console.log(`3. Click on "App settings" or "Permissions"`);
    console.log(`4. Look for a section about "Data access" or "Permissions"`);
    console.log(`5. Ensure the following permissions are enabled:`);
    missingScopes.forEach(scope => {
      console.log(`   - ${scope}`);
    });
    console.log(`\n6. If you can't find these options, you may need to:`);
    console.log(`   - Uninstall the app completely`);
    console.log(`   - Reinstall it from the Shopify App Store`);
    console.log(`   - During installation, ensure all permissions are granted`);

    console.log(`\n🔧 Alternative approach:`);
    console.log(`1. Go to Shopify Partners Dashboard`);
    console.log(`2. Find your app configuration`);
    console.log(`3. Check the "Access scopes" section`);
    console.log(`4. Ensure it includes: ${getCorrectScopesString()}`);
    console.log(`5. If not, update it and redeploy the app`);

    return false;

  } catch (error) {
    console.error(`❌ Error during scope update:`, error);
    return false;
  } finally {
    await prisma.$disconnect();
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('Usage: node scripts/force-scope-update.js <shop-domain>');
  console.log('Example: node scripts/force-scope-update.js vnsaid.myshopify.com');
  process.exit(1);
}

forceScopeUpdate(shopDomain);
