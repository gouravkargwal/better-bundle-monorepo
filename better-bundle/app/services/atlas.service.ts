async function activateAtlasWebPixel(admin: any, shopDomain: string) {
  try {
    // Get the backend URL from environment or use a default
    const backendUrl = process.env.BACKEND_URL;

    const webPixelSettings = {
      backend_url: backendUrl,
    };

    // First, try to create the web pixel
    const createMutation = `
      mutation webPixelCreate($webPixel: WebPixelInput!) {
        webPixelCreate(webPixel: $webPixel) {
          userErrors {
            code
            field
            message
          }
          webPixel {
            id
            settings
          }
        }
      }
    `;

    const createResponse = await admin.graphql(createMutation, {
      variables: {
        webPixel: {
          settings: JSON.stringify(webPixelSettings),
        },
      },
    });

    const createResponseJson = await createResponse.json();

    // Check if creation was successful
    if (
      createResponseJson.data?.webPixelCreate?.userErrors?.length === 0 &&
      createResponseJson.data?.webPixelCreate?.webPixel
    ) {
      console.log(
        "✅ Atlas web pixel created successfully:",
        createResponseJson.data.webPixelCreate.webPixel.id,
      );
      return createResponseJson.data.webPixelCreate.webPixel;
    }

    // If creation failed due to "TAKEN" error, try to update existing web pixel
    const hasTakenError =
      createResponseJson.data?.webPixelCreate?.userErrors?.some(
        (error: any) => error.code === "TAKEN",
      );

    if (hasTakenError) {
      console.log("🔄 Web pixel already exists, attempting to update...");

      // First, get the existing web pixel ID
      const query = `
        query {
          webPixels(first: 1) {
            edges {
              node {
                id
                settings
              }
            }
          }
        }
      `;

      const queryResponse = await admin.graphql(query);
      const queryResponseJson = await queryResponse.json();

      if (queryResponseJson.data?.webPixels?.edges?.length > 0) {
        const webPixelId = queryResponseJson.data.webPixels.edges[0].node.id;

        // Update the existing web pixel
        const updateMutation = `
          mutation webPixelUpdate($id: ID!, $webPixel: WebPixelInput!) {
            webPixelUpdate(id: $id, webPixel: $webPixel) {
              userErrors {
                code
                field
                message
              }
              webPixel {
                id
                settings
              }
            }
          }
        `;

        const updateResponse = await admin.graphql(updateMutation, {
          variables: {
            id: webPixelId,
            webPixel: {
              settings: JSON.stringify(webPixelSettings),
            },
          },
        });

        const updateResponseJson = await updateResponse.json();

        if (
          updateResponseJson.data?.webPixelUpdate?.userErrors?.length === 0 &&
          updateResponseJson.data?.webPixelUpdate?.webPixel
        ) {
          console.log(
            "✅ Atlas web pixel updated successfully:",
            updateResponseJson.data.webPixelUpdate.webPixel.id,
          );
          return updateResponseJson.data.webPixelUpdate.webPixel;
        } else {
          console.error(
            "❌ Web pixel update errors:",
            updateResponseJson.data?.webPixelUpdate?.userErrors,
          );
        }
      }
    } else {
      // Other creation errors
      console.error(
        "❌ Web pixel creation errors:",
        createResponseJson.data?.webPixelCreate?.userErrors,
      );
    }

    throw new Error("Failed to create or update web pixel");
  } catch (error) {
    console.error("❌ Failed to activate Atlas web pixel:", error);
    // Don't throw the error to prevent breaking the entire afterAuth flow
    // The app can still function without the web pixel
  }
}

export { activateAtlasWebPixel };
