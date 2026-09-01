import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_employee_welcome_email(
    email: str, full_name: str, employee_code: str, temp_password: str
) -> bool:
    """
    Sends a welcome email containing employee_code, temporary password, and login URL.
    Returns True if sent successfully, False if SMTP is unconfigured or error occurs.
    Logs error server-side without logging the temporary password.
    """
    if not (settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_APP_PASSWORD):
        logger.warning(f"SMTP is not configured. Unable to send welcome email to {email}.")
        return False

    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    login_url = f"{settings.FRONTEND_URL}/login"

    subject = "Welcome to Teamloom — Account Created"
    body_html = f"""
    <html>
      <body style="font-family: sans-serif; color: #333;">
        <h2>Welcome to Teamloom</h2>
        <p>Hello {full_name},</p>
        <p>Your account has been created by your administrator.</p>
        <div style="background-color: #f4f6f8; padding: 15px; border-radius: 8px; margin: 15px 0;">
          <p><strong>Employee Code:</strong> {employee_code}</p>
          <p><strong>Email:</strong> {email}</p>
          <p><strong>Temporary Password:</strong> <code>{temp_password}</code></p>
        </div>
        <p><strong>Important:</strong> You must change your temporary password upon your first login.</p>
        <p><a href="{login_url}" style="background-color: #3FA88F; color: white; padding: 10px 18px; text-decoration: none; border-radius: 4px; display: inline-block;">Log In Now</a></p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = email
    msg.attach(MIMEText(body_html, "html"))

    try:
        smtp_password = settings.SMTP_APP_PASSWORD.replace(" ", "").strip()
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, smtp_password)
            server.send_message(msg)
        logger.info(f"Welcome email successfully sent to {email}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {e}")
        return False
