import prisma from "app/db.server";

const getShop = async (shopDomain: string) => {
  const shop = await prisma.shop.findUnique({
    where: { shopDomain },
  });
  return shop;
};

export { getShop };
