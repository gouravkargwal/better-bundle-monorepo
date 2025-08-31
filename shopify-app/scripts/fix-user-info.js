import { PrismaClient } from '@prisma/client';
import fetch from 'node-fetch';

const prisma = new PrismaClient();

async function fetchAndUpdateUserInfo(shopDomain) {
  console.log(`👤 Fetching user info for shop: ${shopDomain}`);

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

    console.log(`📋 Session found:`, {
      id: session.id,
      shop: session.shop,
      hasAccessToken: !!session.accessToken,
      currentEmail: session.email,
      currentFirstName: session.firstName,
      currentLastName: session.lastName
    });

    // Fetch shop information from Shopify API
    const shopResponse = await fetch(`https://${shopDomain}/admin/api/2024-01/shop.json`, {
      headers: {
        'X-Shopify-Access-Token': session.accessToken,
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
    const updatedSession = await prisma.session.update({
      where: { id: `offline_${shopDomain}` },
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
          accessToken: session.accessToken,
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

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.error('❌ Please provide a shop domain as an argument');
  console.log('Usage: node fix-user-info.js <shop-domain>');
  console.log('Example: node fix-user-info.js mystore.myshopify.com');
  process.exit(1);
}

// Run the fix
fetchAndUpdateUserInfo(shopDomain)
  .then((success) => {
    if (success) {
      console.log(`✅ User info fix completed successfully for ${shopDomain}`);
    } else {
      console.log(`❌ User info fix failed for ${shopDomain}`);
    }
  })
  .catch((error) => {
    console.error('❌ Unexpected error:', error);
  })
  .finally(() => {
    prisma.$disconnect();
  });
