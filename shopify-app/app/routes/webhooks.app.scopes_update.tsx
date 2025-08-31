import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { payload, session, topic, shop } = await authenticate.webhook(request);
  console.log(`Received ${topic} webhook for ${shop}`);

  const current = payload.current as string[];
  if (session) {
    // Convert array to comma-separated string to match the expected format
    const scopeString = current.join(',');
    console.log(`🔄 Updating session scopes for ${shop}: ${scopeString}`);
    
    await prisma.session.update({
      where: {
        id: session.id,
      },
      data: {
        scope: scopeString,
      },
    });
    
    console.log(`✅ Session scopes updated successfully`);
  }
  return new Response();
};
