import { PrismaClient } from '@prisma/client';
import fetch from 'node-fetch';

const prisma = new PrismaClient();

// Define required scopes
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

async function fetchAndUpdateUserInfo(shopDomain, accessToken) {
  try {
    console.log(`👤 Fetching user info for shop: ${shopDomain}`);

    // Fetch shop information from Shopify API
    const shopResponse = await fetch(`https://${shopDomain}/admin/api/2024-01/shop.json`, {
      headers: {
        'X-Shopify-Access-Token': accessToken,
        'Content-Type': 'application/json',
      },
    });

    if (!shopResponse.ok) {
      console.error(`❌ Failed to fetch shop info: ${shopResponse.status} ${shopResponse.statusText}`);
      return false;
    }

    const shopData = await shopResponse.json();
    const shop = shopData.shop;

    console.log(`📊 Shop data received:`, {
      name: shop.name,
      email: shop.email,
      domain: shop.domain,
      currency: shop.currency
    });

    // Update session with user information
    const sessionId = `offline_${shopDomain}`;
    const updatedSession = await prisma.session.update({
      where: { id: sessionId },
      data: {
        email: shop.email,
        firstName: shop.name?.split(' ')[0] || null,
        lastName: shop.name?.split(' ').slice(1).join(' ') || null,
      },
    });

    console.log(`✅ Session updated with user info:`, {
      email: updatedSession.email,
      firstName: updatedSession.firstName,
      lastName: updatedSession.lastName
    });

    // Also update the shop record with email if it doesn't have one
    const existingShop = await prisma.shop.findUnique({
      where: { shopDomain }
    });

    if (existingShop) {
      const updateData = {};
      if (!existingShop.email) updateData.email = shop.email;
      if (!existingShop.currencyCode) updateData.currencyCode = shop.currency;
      if (!existingShop.moneyFormat) updateData.moneyFormat = shop.money_format;

      if (Object.keys(updateData).length > 0) {
        await prisma.shop.update({
          where: { shopDomain },
          data: updateData
        });
        console.log(`✅ Shop record updated with:`, updateData);
      } else {
        console.log(`✅ Shop record already has all required fields`);
      }
    } else {
      console.log(`🏪 Creating new shop record`);
      await prisma.shop.create({
        data: {
          shopId: shopDomain,
          shopDomain: shopDomain,
          accessToken: accessToken,
          email: shop.email,
          currencyCode: shop.currency,
          moneyFormat: shop.money_format,
          planType: "Free",
          isActive: true
        }
      });
      console.log(`✅ Shop record created`);
    }

    return true;

  } catch (error) {
    console.error(`❌ Error fetching user info:`, error);
    return false;
  }
}

async function fixAllSessionIssues(shopDomain) {
  console.log(`🔧 Fixing all session issues for shop: ${shopDomain}`);

  try {
    // Get the session
    const session = await prisma.session.findUnique({
      where: { id: `offline_${shopDomain}` }
    });

    if (!session) {
      console.log(`❌ No session found for ${shopDomain}`);
      return false;
    }

    if (!session.accessToken) {
      console.log(`❌ No access token found for ${shopDomain}`);
      return false;
    }

    console.log(`📋 Current session state:`, {
      id: session.id,
      shop: session.shop,
      scope: session.scope,
      email: session.email,
      firstName: session.firstName,
      lastName: session.lastName
    });

    let scopesFixed = false;
    let userInfoFixed = false;

    // Fix scopes if needed
    if (!hasRequiredScopes(session.scope)) {
      console.log(`🔄 Fixing scopes...`);
      const correctScopes = getCorrectScopesString();

      await prisma.session.update({
        where: { id: `offline_${shopDomain}` },
        data: { scope: correctScopes }
      });

      console.log(`✅ Scopes updated to: ${correctScopes}`);
      scopesFixed = true;
    } else {
      console.log(`✅ Scopes are already correct`);
      scopesFixed = true;
    }

    // Fix user info if needed
    if (!session.email || !session.firstName) {
      console.log(`🔄 Fixing user info...`);
      userInfoFixed = await fetchAndUpdateUserInfo(shopDomain, session.accessToken);
    } else {
      console.log(`✅ User info already available`);
      userInfoFixed = true;
    }

    // Get final session state
    const finalSession = await prisma.session.findUnique({
      where: { id: `offline_${shopDomain}` }
    });

    console.log(`📋 Final session state:`, {
      scope: finalSession.scope,
      email: finalSession.email,
      firstName: finalSession.firstName,
      lastName: finalSession.lastName
    });

    const success = scopesFixed && userInfoFixed;
    console.log(`✅ Session fix completed:`, { success, scopesFixed, userInfoFixed });

    return success;

  } catch (error) {
    console.error(`❌ Error fixing session issues:`, error);
    return false;
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.error('❌ Please provide a shop domain as an argument');
  console.log('Usage: node fix-all-session-issues.js <shop-domain>');
  console.log('Example: node fix-all-session-issues.js mystore.myshopify.com');
  process.exit(1);
}

// Run the comprehensive fix
fixAllSessionIssues(shopDomain)
  .then((success) => {
    if (success) {
      console.log(`✅ All session issues fixed successfully for ${shopDomain}`);
    } else {
      console.log(`❌ Session fix failed for ${shopDomain}`);
    }
  })
  .catch((error) => {
    console.error('❌ Unexpected error:', error);
  })
  .finally(() => {
    prisma.$disconnect();
  });
