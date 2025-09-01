import { SendPulseEmailService } from "../utils/sendpulse-email";
import { Logger } from "../utils/logger";

export interface EmailNotificationConfig {
  userEmail?: string;
  shopDomain: string;
  jobId: string;
}

// Send analysis started email notification
export const sendAnalysisStartedEmail = async (
  config: EmailNotificationConfig
): Promise<void> => {
  const { userEmail, shopDomain, jobId } = config;
  
  try {
    Logger.info("Sending analysis started email notification", { jobId });

    const emailStartTime = Date.now();
    const emailService = SendPulseEmailService.getInstance();
    await emailService.sendAnalysisStartedNotification(
      userEmail || "admin@example.com", // TODO: Get actual user email from shop data
      shopDomain
    );
    const emailDuration = Date.now() - emailStartTime;

    Logger.performance("Analysis started email sending", emailDuration, {
      jobId,
    });
    Logger.info("Analysis started email sent successfully", { jobId });
  } catch (emailError) {
    Logger.warn("Failed to send analysis started email", {
      jobId,
      error: emailError.message,
    });
  }
};

// Send analysis completion email notification
export const sendAnalysisCompletionEmail = async (
  config: EmailNotificationConfig,
  isSuccess: boolean,
  errorMessage?: string
): Promise<void> => {
  const { userEmail, shopDomain, jobId } = config;
  
  try {
    const emailType = isSuccess ? "success" : "failure";
    Logger.info(`Sending ${emailType} email notification`, { jobId });

    const emailStartTime = Date.now();
    const emailService = SendPulseEmailService.getInstance();
    await emailService.sendAnalysisCompleteNotification(
      userEmail || "admin@example.com", // TODO: Get actual user email from shop data
      shopDomain,
      isSuccess,
      errorMessage
    );
    const emailDuration = Date.now() - emailStartTime;

    Logger.performance(`${emailType} email sending`, emailDuration, { jobId });
    Logger.info(`${emailType} email sent successfully`, { jobId });
  } catch (emailError) {
    Logger.warn(`Failed to send ${isSuccess ? "success" : "failure"} email`, {
      jobId,
      error: emailError.message,
    });
  }
};
