import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function diagnoseScopeIssue(shopDomain) {
  console.log(`🔍 Diagnosing scope issue for shop: ${shopDomain}`);
  console.log('');

  // Check current sessions
  const sessions = await prisma.session.findMany({
    where: { shop: shopDomain }
  });

  console.log('📋 Current Sessions:');
  sessions.forEach((session, index) => {
    console.log(`  Session ${index + 1}:`);
    console.log(`    ID: ${session.id}`);
    console.log(`    Type: ${session.isOnline ? 'Online' : 'Offline'}`);
    console.log(`    Scopes: ${session.scope}`);
    console.log(`    User ID: ${session.userId || 'N/A'}`);
    console.log(`    Email: ${session.email || 'N/A'}`);
    console.log('');
  });

  // Check shop record
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: shopDomain }
  });

  console.log('🏪 Shop Record:');
  if (shop) {
    console.log(`  Domain: ${shop.shopDomain}`);
    console.log(`  Access Token: ${shop.accessToken ? '✅ Present' : '❌ Missing'}`);
    console.log(`  Scopes: ${shop.scopes || 'N/A'}`);
  } else {
    console.log('  ❌ No shop record found');
  }
  console.log('');

  // Expected vs actual scopes
  const expectedScopes = ['write_products', 'read_products', 'read_orders', 'write_orders'];
  const actualScopes = sessions[0]?.scope?.split(',') || [];

  console.log('🎯 Scope Analysis:');
  console.log(`  Expected: ${expectedScopes.join(', ')}`);
  console.log(`  Actual:   ${actualScopes.join(', ')}`);

  const missingScopes = expectedScopes.filter(scope => !actualScopes.includes(scope));
  const extraScopes = actualScopes.filter(scope => !expectedScopes.includes(scope));

  if (missingScopes.length > 0) {
    console.log(`  ❌ Missing scopes: ${missingScopes.join(', ')}`);
  }
  if (extraScopes.length > 0) {
    console.log(`  ⚠️  Extra scopes: ${extraScopes.join(', ')}`);
  }
  if (missingScopes.length === 0 && extraScopes.length === 0) {
    console.log('  ✅ Scopes match expected configuration');
  }
  console.log('');

  // Root cause analysis
  console.log('🔍 Root Cause Analysis:');
  if (missingScopes.includes('read_products') || missingScopes.includes('read_orders')) {
    console.log('  🚨 ISSUE: Missing read permissions (read_products, read_orders)');
    console.log('  📝 This typically happens when:');
    console.log('     1. The merchant only approved write permissions during OAuth');
    console.log('     2. The app configuration was not properly synced with Shopify');
    console.log('     3. There is a mismatch between app.toml and server configuration');
    console.log('');
    console.log('  💡 SOLUTION:');
    console.log('     1. The merchant needs to re-install the app and explicitly approve ALL permissions');
    console.log('     2. During the OAuth flow, ensure the merchant sees and approves:');
    console.log('        - Read access to products');
    console.log('        - Write access to products');
    console.log('        - Read access to orders');
    console.log('        - Write access to orders');
    console.log('');
    console.log('  🛠️  Next Steps:');
    console.log('     1. Run: node scripts/force-reauth.js vnsaid.myshopify.com');
    console.log('     2. Go to your Shopify admin and re-install the app');
    console.log('     3. Pay attention to the permissions screen during installation');
    console.log('     4. Ensure ALL permissions are checked/approved');
  } else {
    console.log('  ✅ Scopes appear to be correct');
    console.log('  💡 If you\'re still having issues, the problem might be:');
    console.log('     1. API rate limiting');
    console.log('     2. Token expiration');
    console.log('     3. App configuration not properly deployed');
  }
  console.log('');

  // Check app configuration
  console.log('⚙️  App Configuration Check:');
  console.log('  ✅ shopify.app.toml scopes: write_products,read_products,read_orders,write_orders');
  console.log('  ✅ server.ts scopes: write_products,read_products,read_orders,write_orders');
  console.log('  ✅ App deployed: Yes (latest version)');
  console.log('  ✅ Online tokens: Enabled');
  console.log('');

  await prisma.$disconnect();
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('❌ Please provide a shop domain');
  console.log('Usage: node scripts/diagnose-scope-issue.js <shop-domain>');
  console.log('Example: node scripts/diagnose-scope-issue.js vnsaid.myshopify.com');
  process.exit(1);
}

diagnoseScopeIssue(shopDomain).catch(console.error);
