"""
Billing Notification Service

This service handles sending notifications for billing events including
invoices, payments, fraud alerts, and billing summaries.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import httpx
from prisma import Prisma

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of billing notifications"""
    INVOICE_GENERATED = "invoice_generated"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_OVERDUE = "payment_overdue"
    FRAUD_ALERT = "fraud_alert"
    BILLING_SUMMARY = "billing_summary"
    PLAN_CHANGED = "plan_changed"
    BILLING_SUSPENDED = "billing_suspended"


class NotificationChannel(Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


@dataclass
class NotificationTemplate:
    """Notification template data"""
    subject: str
    body: str
    html_body: Optional[str] = None
    variables: Dict[str, Any] = None


@dataclass
class NotificationRequest:
    """Request to send a notification"""
    shop_id: str
    notification_type: NotificationType
    channel: NotificationChannel
    recipient: str  # email, phone, or webhook URL
    template: NotificationTemplate
    data: Dict[str, Any]
    priority: str = "normal"  # low, normal, high, urgent


class BillingNotificationService:
    """
    Service for sending billing-related notifications.
    """
    
    def __init__(self, prisma: Prisma):
        self.prisma = prisma
        self.email_service_url = "https://api.sendgrid.com/v3/mail/send"  # Example
        self.sms_service_url = "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json"  # Example
        self.timeout = 30.0
    
    async def send_invoice_notification(
        self,
        shop_id: str,
        invoice_data: Dict[str, Any],
        recipient_email: str
    ) -> bool:
        """
        Send invoice generated notification.
        
        Args:
            shop_id: Shop ID
            invoice_data: Invoice data
            recipient_email: Recipient email address
            
        Returns:
            True if sent successfully
        """
        try:
            template = self._get_invoice_template(invoice_data)
            
            request = NotificationRequest(
                shop_id=shop_id,
                notification_type=NotificationType.INVOICE_GENERATED,
                channel=NotificationChannel.EMAIL,
                recipient=recipient_email,
                template=template,
                data=invoice_data,
                priority="normal"
            )
            
            return await self._send_notification(request)
            
        except Exception as e:
            logger.error(f"Error sending invoice notification for shop {shop_id}: {e}")
            return False
    
    async def send_payment_notification(
        self,
        shop_id: str,
        payment_data: Dict[str, Any],
        recipient_email: str,
        payment_status: str
    ) -> bool:
        """
        Send payment notification (received/failed).
        
        Args:
            shop_id: Shop ID
            payment_data: Payment data
            recipient_email: Recipient email address
            payment_status: Payment status (received/failed)
            
        Returns:
            True if sent successfully
        """
        try:
            notification_type = (
                NotificationType.PAYMENT_RECEIVED if payment_status == "received"
                else NotificationType.PAYMENT_FAILED
            )
            
            template = self._get_payment_template(payment_data, payment_status)
            
            request = NotificationRequest(
                shop_id=shop_id,
                notification_type=notification_type,
                channel=NotificationChannel.EMAIL,
                recipient=recipient_email,
                template=template,
                data=payment_data,
                priority="high" if payment_status == "failed" else "normal"
            )
            
            return await self._send_notification(request)
            
        except Exception as e:
            logger.error(f"Error sending payment notification for shop {shop_id}: {e}")
            return False
    
    async def send_fraud_alert(
        self,
        shop_id: str,
        fraud_data: Dict[str, Any],
        recipient_email: str
    ) -> bool:
        """
        Send fraud alert notification.
        
        Args:
            shop_id: Shop ID
            fraud_data: Fraud detection data
            recipient_email: Recipient email address
            
        Returns:
            True if sent successfully
        """
        try:
            template = self._get_fraud_alert_template(fraud_data)
            
            request = NotificationRequest(
                shop_id=shop_id,
                notification_type=NotificationType.FRAUD_ALERT,
                channel=NotificationChannel.EMAIL,
                recipient=recipient_email,
                template=template,
                data=fraud_data,
                priority="urgent"
            )
            
            return await self._send_notification(request)
            
        except Exception as e:
            logger.error(f"Error sending fraud alert for shop {shop_id}: {e}")
            return False
    
    async def send_billing_summary(
        self,
        shop_id: str,
        summary_data: Dict[str, Any],
        recipient_email: str
    ) -> bool:
        """
        Send monthly billing summary.
        
        Args:
            shop_id: Shop ID
            summary_data: Billing summary data
            recipient_email: Recipient email address
            
        Returns:
            True if sent successfully
        """
        try:
            template = self._get_billing_summary_template(summary_data)
            
            request = NotificationRequest(
                shop_id=shop_id,
                notification_type=NotificationType.BILLING_SUMMARY,
                channel=NotificationChannel.EMAIL,
                recipient=recipient_email,
                template=template,
                data=summary_data,
                priority="normal"
            )
            
            return await self._send_notification(request)
            
        except Exception as e:
            logger.error(f"Error sending billing summary for shop {shop_id}: {e}")
            return False
    
    async def send_overdue_payment_reminder(
        self,
        shop_id: str,
        invoice_data: Dict[str, Any],
        recipient_email: str
    ) -> bool:
        """
        Send overdue payment reminder.
        
        Args:
            shop_id: Shop ID
            invoice_data: Invoice data
            recipient_email: Recipient email address
            
        Returns:
            True if sent successfully
        """
        try:
            template = self._get_overdue_payment_template(invoice_data)
            
            request = NotificationRequest(
                shop_id=shop_id,
                notification_type=NotificationType.PAYMENT_OVERDUE,
                channel=NotificationChannel.EMAIL,
                recipient=recipient_email,
                template=template,
                data=invoice_data,
                priority="high"
            )
            
            return await self._send_notification(request)
            
        except Exception as e:
            logger.error(f"Error sending overdue payment reminder for shop {shop_id}: {e}")
            return False
    
    async def _send_notification(self, request: NotificationRequest) -> bool:
        """
        Send notification via the specified channel.
        
        Args:
            request: Notification request
            
        Returns:
            True if sent successfully
        """
        try:
            if request.channel == NotificationChannel.EMAIL:
                return await self._send_email_notification(request)
            elif request.channel == NotificationChannel.SMS:
                return await self._send_sms_notification(request)
            elif request.channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook_notification(request)
            elif request.channel == NotificationChannel.IN_APP:
                return await self._send_in_app_notification(request)
            else:
                logger.error(f"Unsupported notification channel: {request.channel}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    async def _send_email_notification(self, request: NotificationRequest) -> bool:
        """Send email notification."""
        try:
            # Get shop information
            shop = await self.prisma.shop.find_unique(
                where={"id": request.shop_id},
                select={"domain": True, "name": True}
            )
            
            if not shop:
                logger.error(f"Shop {request.shop_id} not found")
                return False
            
            # Prepare email data
            email_data = {
                "personalizations": [
                    {
                        "to": [{"email": request.recipient}],
                        "subject": request.template.subject
                    }
                ],
                "from": {
                    "email": "billing@betterbundle.app",
                    "name": "Better Bundle Billing"
                },
                "content": [
                    {
                        "type": "text/plain",
                        "value": request.template.body
                    }
                ]
            }
            
            # Add HTML content if available
            if request.template.html_body:
                email_data["content"].append({
                    "type": "text/html",
                    "value": request.template.html_body
                })
            
            # Send email (using SendGrid as example)
            headers = {
                "Authorization": f"Bearer {self._get_sendgrid_api_key()}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.email_service_url,
                    json=email_data,
                    headers=headers
                )
                response.raise_for_status()
            
            # Log notification
            await self._log_notification(request, "sent")
            
            logger.info(f"Email notification sent to {request.recipient} for shop {request.shop_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            await self._log_notification(request, "failed", str(e))
            return False
    
    async def _send_sms_notification(self, request: NotificationRequest) -> bool:
        """Send SMS notification."""
        try:
            # Prepare SMS data (using Twilio as example)
            sms_data = {
                "To": request.recipient,
                "From": "+1234567890",  # Your Twilio number
                "Body": request.template.body
            }
            
            # Send SMS
            auth = (self._get_twilio_account_sid(), self._get_twilio_auth_token())
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.sms_service_url.format(self._get_twilio_account_sid()),
                    data=sms_data,
                    auth=auth
                )
                response.raise_for_status()
            
            # Log notification
            await self._log_notification(request, "sent")
            
            logger.info(f"SMS notification sent to {request.recipient} for shop {request.shop_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS notification: {e}")
            await self._log_notification(request, "failed", str(e))
            return False
    
    async def _send_webhook_notification(self, request: NotificationRequest) -> bool:
        """Send webhook notification."""
        try:
            # Prepare webhook payload
            webhook_data = {
                "notification_type": request.notification_type.value,
                "shop_id": request.shop_id,
                "data": request.data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send webhook
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    request.recipient,
                    json=webhook_data,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
            
            # Log notification
            await self._log_notification(request, "sent")
            
            logger.info(f"Webhook notification sent to {request.recipient} for shop {request.shop_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            await self._log_notification(request, "failed", str(e))
            return False
    
    async def _send_in_app_notification(self, request: NotificationRequest) -> bool:
        """Send in-app notification."""
        try:
            # Store notification in database for in-app display
            await self.prisma.billingEvent.create({
                "data": {
                    "notification_type": request.notification_type.value,
                    "title": request.template.subject,
                    "message": request.template.body,
                    "data": request.data,
                    "priority": request.priority
                },
                "metadata": {
                    "channel": request.channel.value,
                    "sent_at": datetime.utcnow().isoformat()
                },
                "shopId": request.shop_id,
                "type": "notification_sent",
                "occurredAt": datetime.utcnow()
            })
            
            # Log notification
            await self._log_notification(request, "sent")
            
            logger.info(f"In-app notification stored for shop {request.shop_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending in-app notification: {e}")
            await self._log_notification(request, "failed", str(e))
            return False
    
    def _get_invoice_template(self, invoice_data: Dict[str, Any]) -> NotificationTemplate:
        """Get invoice notification template."""
        invoice_number = invoice_data.get("invoice_number", "N/A")
        total = invoice_data.get("total", 0)
        due_date = invoice_data.get("due_date", "N/A")
        
        subject = f"Better Bundle Invoice #{invoice_number} - ${total}"
        
        body = f"""
Dear Merchant,

Your Better Bundle invoice #{invoice_number} has been generated.

Invoice Details:
- Amount: ${total}
- Due Date: {due_date}
- Period: {invoice_data.get('period_start', 'N/A')} to {invoice_data.get('period_end', 'N/A')}

You can view and pay your invoice in your Better Bundle dashboard.

Thank you for using Better Bundle!

Best regards,
Better Bundle Team
        """.strip()
        
        html_body = f"""
<html>
<body>
    <h2>Better Bundle Invoice #{invoice_number}</h2>
    <p>Dear Merchant,</p>
    <p>Your Better Bundle invoice #{invoice_number} has been generated.</p>
    
    <h3>Invoice Details:</h3>
    <ul>
        <li><strong>Amount:</strong> ${total}</li>
        <li><strong>Due Date:</strong> {due_date}</li>
        <li><strong>Period:</strong> {invoice_data.get('period_start', 'N/A')} to {invoice_data.get('period_end', 'N/A')}</li>
    </ul>
    
    <p>You can view and pay your invoice in your <a href="https://betterbundle.app/dashboard">Better Bundle dashboard</a>.</p>
    
    <p>Thank you for using Better Bundle!</p>
    
    <p>Best regards,<br>Better Bundle Team</p>
</body>
</html>
        """.strip()
        
        return NotificationTemplate(
            subject=subject,
            body=body,
            html_body=html_body,
            variables=invoice_data
        )
    
    def _get_payment_template(self, payment_data: Dict[str, Any], status: str) -> NotificationTemplate:
        """Get payment notification template."""
        invoice_number = payment_data.get("invoice_number", "N/A")
        amount = payment_data.get("amount", 0)
        
        if status == "received":
            subject = f"Payment Received - Invoice #{invoice_number}"
            body = f"""
Dear Merchant,

We have successfully received your payment for invoice #{invoice_number}.

Payment Details:
- Amount: ${amount}
- Invoice: #{invoice_number}
- Payment Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Thank you for your payment!

Best regards,
Better Bundle Team
            """.strip()
        else:
            subject = f"Payment Failed - Invoice #{invoice_number}"
            body = f"""
Dear Merchant,

We were unable to process your payment for invoice #{invoice_number}.

Payment Details:
- Amount: ${amount}
- Invoice: #{invoice_number}
- Attempt Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Please update your payment method and try again. You can manage your billing in your Better Bundle dashboard.

If you continue to experience issues, please contact our support team.

Best regards,
Better Bundle Team
            """.strip()
        
        return NotificationTemplate(
            subject=subject,
            body=body,
            variables=payment_data
        )
    
    def _get_fraud_alert_template(self, fraud_data: Dict[str, Any]) -> NotificationTemplate:
        """Get fraud alert template."""
        risk_level = fraud_data.get("risk_level", "unknown")
        shop_id = fraud_data.get("shop_id", "N/A")
        
        subject = f"URGENT: Fraud Alert - Shop {shop_id}"
        
        body = f"""
URGENT FRAUD ALERT

We have detected suspicious activity in your Better Bundle account.

Alert Details:
- Shop ID: {shop_id}
- Risk Level: {risk_level.upper()}
- Detected At: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
- Confidence Score: {fraud_data.get('confidence_score', 'N/A')}

Detected Fraud Types:
{', '.join(fraud_data.get('fraud_types', []))}

Recommendations:
{chr(10).join(f"- {rec}" for rec in fraud_data.get('recommendations', []))}

IMMEDIATE ACTION REQUIRED:
1. Review your account activity
2. Verify all recent transactions
3. Contact our support team immediately

This is an automated alert. Please do not ignore this message.

Best regards,
Better Bundle Security Team
        """.strip()
        
        return NotificationTemplate(
            subject=subject,
            body=body,
            variables=fraud_data
        )
    
    def _get_billing_summary_template(self, summary_data: Dict[str, Any]) -> NotificationTemplate:
        """Get billing summary template."""
        period = summary_data.get("period", "N/A")
        total_revenue = summary_data.get("total_revenue", 0)
        total_fees = summary_data.get("total_fees", 0)
        
        subject = f"Better Bundle Monthly Summary - {period}"
        
        body = f"""
Dear Merchant,

Here's your Better Bundle monthly performance summary for {period}.

Performance Summary:
- Total Attributed Revenue: ${total_revenue}
- Your Fees: ${total_fees}
- Average Fee Rate: {(total_fees/total_revenue*100):.1f}% (if total_revenue > 0 else 0)

Monthly Breakdown:
{chr(10).join(f"- {month.get('month', 'N/A')}: ${month.get('revenue', 0)} revenue, ${month.get('fee', 0)} fee" for month in summary_data.get('monthly_breakdown', []))}

Thank you for using Better Bundle!

Best regards,
Better Bundle Team
        """.strip()
        
        return NotificationTemplate(
            subject=subject,
            body=body,
            variables=summary_data
        )
    
    def _get_overdue_payment_template(self, invoice_data: Dict[str, Any]) -> NotificationTemplate:
        """Get overdue payment template."""
        invoice_number = invoice_data.get("invoice_number", "N/A")
        total = invoice_data.get("total", 0)
        days_overdue = invoice_data.get("days_overdue", 0)
        
        subject = f"URGENT: Overdue Payment - Invoice #{invoice_number}"
        
        body = f"""
URGENT: PAYMENT OVERDUE

Your Better Bundle invoice #{invoice_number} is now {days_overdue} days overdue.

Invoice Details:
- Amount: ${total}
- Invoice: #{invoice_number}
- Days Overdue: {days_overdue}

IMMEDIATE ACTION REQUIRED:
Please pay this invoice immediately to avoid service interruption.

You can pay online at: https://betterbundle.app/dashboard/billing

If you have already paid, please contact our support team.

Best regards,
Better Bundle Billing Team
        """.strip()
        
        return NotificationTemplate(
            subject=subject,
            body=body,
            variables=invoice_data
        )
    
    async def _log_notification(
        self,
        request: NotificationRequest,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Log notification attempt."""
        try:
            await self.prisma.billingEvent.create({
                "data": {
                    "notification_type": request.notification_type.value,
                    "channel": request.channel.value,
                    "recipient": request.recipient,
                    "status": status,
                    "error_message": error_message,
                    "priority": request.priority
                },
                "metadata": {
                    "template_subject": request.template.subject,
                    "sent_at": datetime.utcnow().isoformat()
                },
                "shopId": request.shop_id,
                "type": "notification_attempt",
                "occurredAt": datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
    
    def _get_sendgrid_api_key(self) -> str:
        """Get SendGrid API key from environment."""
        import os
        return os.getenv("SENDGRID_API_KEY", "")
    
    def _get_twilio_account_sid(self) -> str:
        """Get Twilio account SID from environment."""
        import os
        return os.getenv("TWILIO_ACCOUNT_SID", "")
    
    def _get_twilio_auth_token(self) -> str:
        """Get Twilio auth token from environment."""
        import os
        return os.getenv("TWILIO_AUTH_TOKEN", "")
    
    async def get_notification_history(
        self,
        shop_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get notification history for a shop."""
        try:
            events = await self.prisma.billingEvent.findMany(
                where={
                    "shopId": shop_id,
                    "type": "notification_attempt"
                },
                orderBy={
                    "occurredAt": "desc"
                },
                take=limit
            )
            
            return [
                {
                    "id": event.id,
                    "notification_type": event.data.get("notification_type"),
                    "channel": event.data.get("channel"),
                    "recipient": event.data.get("recipient"),
                    "status": event.data.get("status"),
                    "priority": event.data.get("priority"),
                    "sent_at": event.occurredAt.isoformat(),
                    "error_message": event.data.get("error_message")
                }
                for event in events
            ]
            
        except Exception as e:
            logger.error(f"Error getting notification history for shop {shop_id}: {e}")
            return []
