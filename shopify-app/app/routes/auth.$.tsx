import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const x = await authenticate.admin(request);
    console.log(x, "sdasdasdad asd asd asd a da d asd as ");
    return null;
  } catch (error) {
    console.log(error, "error");
    return null;
  }
};
