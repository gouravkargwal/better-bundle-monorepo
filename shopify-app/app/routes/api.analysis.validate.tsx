import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { DataValidationService } from "../features/data-validation";
import type { ApiResponse } from "../types";

export const action = async ({ request }: ActionFunctionArgs) => {
  await authenticate.admin(request);

  if (request.method !== "POST") {
    return json<ApiResponse>(
      { success: false, error: "Method not allowed" },
      { status: 405 },
    );
  }

  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;

    const validationService = new DataValidationService();
    const validation = await validationService.validateStoreData(shopId);

    if (!validation.isValid) {
      return json<ApiResponse>(
        {
          success: false,
          error: validation.error,
          errorType: validation.errorType,
          recommendations: validation.recommendations,
          data: {
            orderCount: validation.orderCount,
            productCount: validation.productCount,
          },
        },
        { status: 400 },
      );
    }

    return json<ApiResponse>({
      success: true,
      data: {
        orderCount: validation.orderCount,
        productCount: validation.productCount,
        recommendations: validation.recommendations,
      },
    });
  } catch (error) {
    console.error("Error validating store data:", error);
    return json<ApiResponse>(
      {
        success: false,
        error: "Failed to validate store data",
        errorType: "api-error",
      },
      { status: 500 },
    );
  }
};
