import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const shops = await prisma.shops.findMany({
    where: {
      shop_domain: { contains: "cpofq5bp" }
    }
  });
  console.log(shops);

  if (shops.length > 0) {
    const subs = await prisma.shop_subscriptions.findMany({
      where: {
        shop_id: shops[0].id
      }
    });
    console.log(subs);
  }
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });