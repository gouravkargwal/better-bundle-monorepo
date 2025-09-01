import * as sendpulse from "sendpulse-api";

export interface EmailData {
  to: string;
  subject: string;
  html: string;
  text?: string;
}

export class SendPulseEmailService {
  private static instance: SendPulseEmailService;
  private isInitialized = false;

  private constructor() {}

  static getInstance(): SendPulseEmailService {
    if (!SendPulseEmailService.instance) {
      SendPulseEmailService.instance = new SendPulseEmailService();
    }
    return SendPulseEmailService.instance;
  }

  private initialize() {
    if (this.isInitialized) return;

    const userId = process.env.SENDPULSE_USER_ID;
    const secret = process.env.SENDPULSE_SECRET;

    if (!userId || !secret) {
      throw new Error("SendPulse credentials not configured. Please set SENDPULSE_USER_ID and SENDPULSE_SECRET environment variables.");
    }

    sendpulse.init(userId, secret, "https://api.sendpulse.com", () => {
      console.log("✅ SendPulse initialized successfully");
    });
    this.isInitialized = true;
  }

  /**
   * Send an email using SendPulse
   */
  async sendEmail(emailData: EmailData): Promise<boolean> {
    try {
      this.initialize();

      const emailOptions = {
        html: emailData.html,
        text: emailData.text || this.stripHtml(emailData.html),
        subject: emailData.subject,
        from: {
          name: "BetterBundle",
          email: process.env.SENDPULSE_FROM_EMAIL || "noreply@betterbundle.com",
        },
        to: [
          {
            name: emailData.to.split("@")[0], // Use email prefix as name
            email: emailData.to,
          },
        ],
      };

      return new Promise((resolve, reject) => {
        sendpulse.smtpSendMail((data: any) => {
          if (data.result) {
            console.log("✅ Email sent successfully:", data);
            resolve(true);
          } else {
            console.error("❌ Failed to send email:", data);
            reject(new Error(data.message || "Failed to send email"));
          }
        }, emailOptions);
      });
    } catch (error) {
      console.error("❌ SendPulse email error:", error);
      throw error;
    }
  }

  /**
   * Send analysis completion notification
   */
  async sendAnalysisCompleteNotification(
    email: string,
    shopDomain: string,
    success: boolean,
    error?: string
  ): Promise<boolean> {
    const subject = success 
      ? "🎉 Your Bundle Analysis is Complete!" 
      : "❌ Bundle Analysis Failed";

    const html = success 
      ? this.getSuccessEmailTemplate(shopDomain)
      : this.getFailureEmailTemplate(shopDomain, error);

    return this.sendEmail({
      to: email,
      subject,
      html,
    });
  }

  /**
   * Send analysis started notification
   */
  async sendAnalysisStartedNotification(
    email: string,
    shopDomain: string
  ): Promise<boolean> {
    const subject = "🔄 Bundle Analysis Started";
    const html = this.getStartedEmailTemplate(shopDomain);

    return this.sendEmail({
      to: email,
      subject,
      html,
    });
  }

  private getSuccessEmailTemplate(shopDomain: string): string {
    const appUrl = process.env.SHOPIFY_APP_URL || "https://betterbundle.vercel.app";
    
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bundle Analysis Complete</title>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
          .button { display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
          .footer { text-align: center; margin-top: 30px; color: #666; font-size: 14px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>🎉 Bundle Analysis Complete!</h1>
            <p>Your store analysis has finished successfully</p>
          </div>
          <div class="content">
            <h2>Great news!</h2>
            <p>We've completed analyzing your store <strong>${shopDomain}</strong> and found some amazing bundle opportunities to increase your sales.</p>
            
            <h3>What we found:</h3>
            <ul>
              <li>📊 Product performance insights</li>
              <li>🛍️ Bundle recommendations</li>
              <li>💰 Revenue optimization opportunities</li>
              <li>📈 Customer behavior patterns</li>
            </ul>
            
            <p>Ready to see your results and start creating bundles?</p>
            
            <a href="${appUrl}/app/dashboard" class="button">View Your Results</a>
            
            <p><small>This analysis will help you create product bundles that customers love and boost your average order value.</small></p>
          </div>
          <div class="footer">
            <p>BetterBundle - Boost your sales with smart product bundles</p>
            <p>If you have any questions, feel free to reach out to our support team.</p>
          </div>
        </div>
      </body>
      </html>
    `;
  }

  private getFailureEmailTemplate(shopDomain: string, error?: string): string {
    const appUrl = process.env.SHOPIFY_APP_URL || "https://betterbundle.vercel.app";
    
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bundle Analysis Failed</title>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
          .button { display: inline-block; background: #ff6b6b; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
          .error-box { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }
          .footer { text-align: center; margin-top: 30px; color: #666; font-size: 14px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>❌ Bundle Analysis Failed</h1>
            <p>We encountered an issue while analyzing your store</p>
          </div>
          <div class="content">
            <h2>Sorry about that!</h2>
            <p>We weren't able to complete the analysis for your store <strong>${shopDomain}</strong>.</p>
            
            ${error ? `
            <div class="error-box">
              <strong>Error details:</strong><br>
              ${error}
            </div>
            ` : ''}
            
            <p>Don't worry! You can try running the analysis again:</p>
            
            <a href="${appUrl}/app/dashboard" class="button">Try Again</a>
            
            <p><small>If this issue persists, please contact our support team and we'll help you resolve it.</small></p>
          </div>
          <div class="footer">
            <p>BetterBundle - Boost your sales with smart product bundles</p>
            <p>Need help? Contact our support team.</p>
          </div>
        </div>
      </body>
      </html>
    `;
  }

  private getStartedEmailTemplate(shopDomain: string): string {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bundle Analysis Started</title>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
          .footer { text-align: center; margin-top: 30px; color: #666; font-size: 14px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>🔄 Bundle Analysis Started</h1>
            <p>We're analyzing your store data</p>
          </div>
          <div class="content">
            <h2>Analysis in Progress</h2>
            <p>Great! We've started analyzing your store <strong>${shopDomain}</strong> to find the best bundle opportunities.</p>
            
            <h3>What we're doing:</h3>
            <ul>
              <li>📊 Analyzing your product catalog</li>
              <li>🛒 Reviewing customer purchase patterns</li>
              <li>📈 Identifying high-performing products</li>
              <li>🎯 Finding bundle opportunities</li>
            </ul>
            
            <p>This process usually takes 5-10 minutes. You'll receive another email when the analysis is complete!</p>
            
            <p><small>You can also check the progress in your dashboard at any time.</small></p>
          </div>
          <div class="footer">
            <p>BetterBundle - Boost your sales with smart product bundles</p>
            <p>We'll notify you when the analysis is complete.</p>
          </div>
        </div>
      </body>
      </html>
    `;
  }

  private stripHtml(html: string): string {
    return html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
  }
}
