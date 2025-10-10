import { SignJWT } from "jose";

// Handle CORS preflight requests
export const loader = async ({ request }: { request: Request }) => {
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  return new Response("OK", { status: 200 });
};

// The action responds to the POST request from the extension
export const action = async ({ request }: { request: Request }) => {
  const body = await request.json();

  // Create JWT using jose library
  const secret = new TextEncoder().encode(process.env.SHOPIFY_API_SECRET!);

  const token = await new SignJWT({
    changes: body.changes,
  })
    .setProtectedHeader({
      alg: "HS256",
    })
    .setIssuer(process.env.SHOPIFY_API_KEY!)
    .setSubject(body.referenceId)
    .setIssuedAt()
    .setJti(crypto.randomUUID())
    .setExpirationTime("5m") // Token expires in 5 minutes
    .sign(secret);

  return new Response(JSON.stringify({ token }), {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
};
