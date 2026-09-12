import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const updated = await prisma.subscription_plans.updateMany({
    where: {
      name: "Pay As You Go",
    },
    data: {
      cap_amount: 29.00,
    },
  });
  console.log(`Updated ${updated.count} plans.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });