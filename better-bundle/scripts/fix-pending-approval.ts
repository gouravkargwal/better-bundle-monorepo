import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const updated = await prisma.shop_subscriptions.updateMany({
    where: {
      status: "PENDING_APPROVAL",
    },
    data: {
      status: "TRIAL_COMPLETED",
      shopify_status: "CANCELLED",
    },
  });
  console.log(`Updated ${updated.count} subscriptions from PENDING_APPROVAL to TRIAL_COMPLETED.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });