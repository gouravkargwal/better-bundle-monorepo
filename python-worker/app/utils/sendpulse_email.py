"""
SendPulse email service for sending analysis completion notifications
"""

import structlog
import httpx
from typing import Dict, Any, Optional

from app.core.config import settings

logger = structlog.get_logger(__name__)


class SendPulseEmailService:
    """Service for sending emails via SendPulse"""

    def __init__(self):
        self.api_url = "https://api.sendpulse.com"
        self.api_user_id = settings.SENDPULSE_USER_ID
        self.api_secret = settings.SENDPULSE_SECRET
        self.sender_email = settings.SENDPULSE_SENDER_EMAIL
        self.sender_name = settings.SENDPULSE_SENDER_NAME

    async def _get_access_token(self) -> Optional[str]:
        """Get SendPulse access token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/oauth/access_token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.api_user_id,
                        "client_secret": self.api_secret,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("access_token")
                else:
                    logger.error(
                        "Failed to get SendPulse access token",
                        status_code=response.status_code,
                    )
                    return None

        except Exception as e:
            logger.error("Error getting SendPulse access token", error=str(e))
            return None

    async def send_analysis_complete_email(
        self,
        to_email: str,
        shop_domain: str,
        job_id: str,
        analysis_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send analysis completion success email"""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            # Prepare email content
            subject = "🎉 Your Bundle Analysis is Complete!"

            # Extract bundle count from analysis result
            bundle_count = 0
            if analysis_result and analysis_result.get("bundles"):
                bundle_count = len(analysis_result["bundles"])

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Bundle Analysis Complete</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .button {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .stats {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎉 Bundle Analysis Complete!</h1>
                        <p>Your store data has been analyzed successfully</p>
                    </div>
                    
                    <div class="content">
                        <h2>Great news, {shop_domain}!</h2>
                        <p>We've successfully analyzed your store data and discovered optimal product bundles that can help increase your sales.</p>
                        
                        <div class="stats">
                            <h3>📊 Analysis Summary</h3>
                            <p><strong>Bundles Discovered:</strong> {bundle_count}</p>
                            <p><strong>Analysis Job ID:</strong> {job_id}</p>
                            <p><strong>Status:</strong> ✅ Complete</p>
                        </div>
                        
                        <p>Your bundle recommendations are now ready and will be automatically displayed to your customers to increase average order value.</p>
                        
                        <a href="https://{shop_domain}/admin/apps/betterbundle/dashboard" class="button">View Your Dashboard</a>
                        
                        <p><small>You can also check the progress in your dashboard at any time.</small></p>
                    </div>
                    
                    <div class="footer">
                        <p>This email was sent by BetterBundle - Your AI-powered bundle recommendation system</p>
                        <p>If you have any questions, please contact our support team.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Send email via SendPulse
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/smtp/emails",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "email": {
                            "html": html_content,
                            "text": f"Your bundle analysis is complete! {bundle_count} bundles discovered. View your dashboard: https://{shop_domain}/admin/apps/betterbundle/dashboard",
                            "subject": subject,
                            "from": {
                                "name": self.sender_name,
                                "email": self.sender_email,
                            },
                            "to": [{"name": shop_domain, "email": to_email}],
                        }
                    },
                )

                if response.status_code == 200:
                    logger.info(
                        "Analysis completion email sent successfully",
                        to_email=to_email,
                        shop_domain=shop_domain,
                    )
                    return {"success": True, "message_id": response.json().get("id")}
                else:
                    logger.error(
                        "Failed to send analysis completion email",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return {
                        "success": False,
                        "error": f"SendPulse API error: {response.status_code}",
                    }

        except Exception as e:
            logger.error("Error sending analysis completion email", error=str(e))
            return {"success": False, "error": str(e)}

    async def send_analysis_failed_email(
        self, to_email: str, shop_domain: str, job_id: str, error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send analysis failure email"""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            # Prepare email content
            subject = "❌ Bundle Analysis Failed"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Bundle Analysis Failed</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .button {{ display: inline-block; background: #ff6b6b; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .error-box {{ background: #ffe6e6; border: 1px solid #ffcccc; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>❌ Bundle Analysis Failed</h1>
                        <p>We encountered an issue while analyzing your store data</p>
                    </div>
                    
                    <div class="content">
                        <h2>Hello {shop_domain},</h2>
                        <p>Unfortunately, we encountered an issue while analyzing your store data. Don't worry - this is usually a temporary issue that can be resolved.</p>
                        
                        <div class="error-box">
                            <h3>🔍 Error Details</h3>
                            <p><strong>Job ID:</strong> {job_id}</p>
                            <p><strong>Error:</strong> {error or "Unknown error occurred"}</p>
                        </div>
                        
                        <p>We'll automatically retry the analysis, but you can also manually trigger a new analysis from your dashboard.</p>
                        
                        <a href="https://{shop_domain}/admin/apps/betterbundle/dashboard" class="button">Try Again</a>
                        
                        <p><small>If this issue persists, please contact our support team for assistance.</small></p>
                    </div>
                    
                    <div class="footer">
                        <p>This email was sent by BetterBundle - Your AI-powered bundle recommendation system</p>
                        <p>If you have any questions, please contact our support team.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Send email via SendPulse
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/smtp/emails",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "email": {
                            "html": html_content,
                            "text": f"Bundle analysis failed for {shop_domain}. Error: {error or 'Unknown error'}. Try again: https://{shop_domain}/admin/apps/betterbundle/dashboard",
                            "subject": subject,
                            "from": {
                                "name": self.sender_name,
                                "email": self.sender_email,
                            },
                            "to": [{"name": shop_domain, "email": to_email}],
                        }
                    },
                )

                if response.status_code == 200:
                    logger.info(
                        "Analysis failure email sent successfully",
                        to_email=to_email,
                        shop_domain=shop_domain,
                    )
                    return {"success": True, "message_id": response.json().get("id")}
                else:
                    logger.error(
                        "Failed to send analysis failure email",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return {
                        "success": False,
                        "error": f"SendPulse API error: {response.status_code}",
                    }

        except Exception as e:
            logger.error("Error sending analysis failure email", error=str(e))
            return {"success": False, "error": str(e)}

    async def send_analysis_started_email(
        self, to_email: str, shop_domain: str, job_id: str
    ) -> Dict[str, Any]:
        """Send analysis started email"""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            # Prepare email content
            subject = "🔄 Bundle Analysis Started"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Bundle Analysis Started</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .button {{ display: inline-block; background: #4facfe; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .info-box {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔄 Bundle Analysis Started</h1>
                        <p>We're analyzing your store data to discover optimal product bundles</p>
                    </div>
                    
                    <div class="content">
                        <h2>Hello {shop_domain},</h2>
                        <p>Great news! We've started analyzing your store data to discover the best product bundles that can help increase your sales.</p>
                        
                        <div class="info-box">
                            <h3>📋 What we're analyzing:</h3>
                            <ul>
                                <li>📦 Order patterns and customer behavior</li>
                                <li>🛍️ Product relationships and co-purchase data</li>
                                <li>🧠 AI-powered bundle optimization</li>
                                <li>💰 Revenue potential calculations</li>
                            </ul>
                        </div>
                        
                        <p><strong>Estimated completion time:</strong> 2-5 minutes</p>
                        <p><strong>Job ID:</strong> {job_id}</p>
                        
                        <p>You'll receive another email when the analysis is complete with your bundle recommendations.</p>
                        
                        <a href="https://{shop_domain}/admin/apps/betterbundle/dashboard" class="button">View Progress</a>
                        
                        <p><small>You can also check the progress in your dashboard at any time.</small></p>
                    </div>
                    
                    <div class="footer">
                        <p>This email was sent by BetterBundle - Your AI-powered bundle recommendation system</p>
                        <p>If you have any questions, please contact our support team.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Send email via SendPulse
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/smtp/emails",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "email": {
                            "html": html_content,
                            "text": f"Bundle analysis started for {shop_domain}. Estimated completion: 2-5 minutes. Track progress: https://{shop_domain}/admin/apps/betterbundle/dashboard",
                            "subject": subject,
                            "from": {
                                "name": self.sender_name,
                                "email": self.sender_email,
                            },
                            "to": [{"name": shop_domain, "email": to_email}],
                        }
                    },
                )

                if response.status_code == 200:
                    logger.info(
                        "Analysis started email sent successfully",
                        to_email=to_email,
                        shop_domain=shop_domain,
                    )
                    return {"success": True, "message_id": response.json().get("id")}
                else:
                    logger.error(
                        "Failed to send analysis started email",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    return {
                        "success": False,
                        "error": f"SendPulse API error: {response.status_code}",
                    }

        except Exception as e:
            logger.error("Error sending analysis started email", error=str(e))
            return {"success": False, "error": str(e)}
