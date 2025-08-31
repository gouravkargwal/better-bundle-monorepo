import axios from "axios";

export interface AppEventData {
  title: string;
  description: string;
  link?: {
    url: string;
    label: string;
  };
  type: string;
}

export class ShopifyNotificationService {
  /**
   * Send notification to Shopify's native notification box (bell icon)
   * using the App Events API with GraphQL
   */
  static async sendAppEventNotification(
    shopDomain: string,
    accessToken: string,
    event: AppEventData
  ) {
    try {
      const graphqlEndpoint = `https://${shopDomain}/admin/api/2025-07/graphql.json`;
      
      const mutation = `
        mutation AppEventCreate($event: AppEventInput!) {
          appEventCreate(event: $event) {
            userErrors {
              field
              message
            }
            appEvent {
              id
              title
              description
              link {
                label
                url
              }
            }
          }
        }
      `;

      const response = await axios.post(
        graphqlEndpoint,
        {
          query: mutation,
          variables: {
            event: {
              title: event.title,
              description: event.description,
              link: event.link,
              type: event.type,
            },
          },
        },
        {
          headers: {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": accessToken,
          },
          timeout: 10000,
        }
      );

      if (response.data.errors) {
        console.error("❌ GraphQL errors:", response.data.errors);
        throw new Error(`GraphQL errors: ${JSON.stringify(response.data.errors)}`);
      }

      if (response.data.data?.appEventCreate?.userErrors?.length > 0) {
        console.error("❌ User errors:", response.data.data.appEventCreate.userErrors);
        throw new Error(`User errors: ${JSON.stringify(response.data.data.appEventCreate.userErrors)}`);
      }

      console.log("✅ App event notification sent successfully:", response.data.data?.appEventCreate?.appEvent);
      return response.data.data?.appEventCreate?.appEvent;
    } catch (error) {
      console.error("❌ Failed to send app event notification:", error);
      throw error;
    }
  }

  /**
   * Send analysis completion notification
   */
  static async sendAnalysisCompleteNotification(
    shopDomain: string,
    accessToken: string,
    jobId: string,
    success: boolean,
    error?: string
  ) {
    const appUrl = process.env.SHOPIFY_APP_URL || "http://localhost:3000";
    
    const event: AppEventData = {
      title: success 
        ? "Bundle Analysis Completed" 
        : "Bundle Analysis Failed",
      description: success
        ? `Your bundle analysis has been completed successfully. View the results to see product recommendations and insights.`
        : `Bundle analysis failed: ${error || "Unknown error occurred"}. Please try again or contact support.`,
      link: {
        url: `${appUrl}/app/dashboard`,
        label: success ? "View Results" : "Try Again",
      },
      type: success ? "ANALYSIS_SUCCESS" : "ANALYSIS_FAILED",
    };

    return this.sendAppEventNotification(shopDomain, accessToken, event);
  }

  /**
   * Send analysis started notification
   */
  static async sendAnalysisStartedNotification(
    shopDomain: string,
    accessToken: string,
    jobId: string
  ) {
    const appUrl = process.env.SHOPIFY_APP_URL || "http://localhost:3000";
    
    const event: AppEventData = {
      title: "Bundle Analysis Started",
      description: "We're analyzing your store data to generate bundle recommendations. This may take a few minutes.",
      link: {
        url: `${appUrl}/app/dashboard`,
        label: "View Progress",
      },
      type: "ANALYSIS_STARTED",
    };

    return this.sendAppEventNotification(shopDomain, accessToken, event);
  }
}
