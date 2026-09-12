import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const updated = await prisma.shops.updateMany({
    where: {
      suspension_reason: "subscription_pending_approval",
    },
    data: {
      suspension_reason: "trial_completed_subscription_required",
    },
  });
  console.log(`Updated ${updated.count} shops.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });