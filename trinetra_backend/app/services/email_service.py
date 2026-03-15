import structlog
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, PlainTextContent, HtmlContent
from app.core.config import settings

logger = structlog.get_logger()

class EmailService:
    def __init__(self):
        self.client = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME

    def send_email(self, recipient: str, subject: str, body: str) -> dict:
        try:
            html_body = body.replace("\n", "<br>")
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=recipient,
                subject=subject,
                plain_text_content=body,
                html_content=f"<html><body><p>{html_body}</p></body></html>"
            )

            response = self.client.send(message)
            message_id = response.headers.get("X-Message-Id", "")

            logger.info("email_sent",
                recipient=recipient,
                subject=subject,
                status_code=response.status_code,
                message_id=message_id
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "message_id": message_id,
            }

        except Exception as e:
            logger.error("email_send_failed", recipient=recipient, error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

email_service = EmailService()
