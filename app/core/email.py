import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSender(ABC):
    """
    Abstract EmailSender Interface (NFR-3).
    Allows plugging in different email delivery providers (SMTP, Console/Dev, SES, SendGrid)
    strictly via configuration without modifying application service or route code.
    """

    @abstractmethod
    def send_verification_email(self, email: str, full_name: str, token: str) -> bool:
        """Sends an email verification link with single-use token to the registered user."""
        pass

    @abstractmethod
    def send_welcome_email(
        self, email: str, full_name: str, employee_code: str, temp_password: str
    ) -> bool:
        """Sends a welcome email containing employee User ID and initial temporary password."""
        pass


class SMTPEmailSender(EmailSender):
    """
    SMTP implementation of EmailSender.
    Sends transactional HTML emails over TLS via standard smtplib.
    """

    def send_verification_email(self, email: str, full_name: str, token: str) -> bool:
        if not (settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_APP_PASSWORD):
            logger.warning("SMTP is not configured. Falling back to Console logger for verification email.")
            return ConsoleEmailSender().send_verification_email(email, full_name, token)

        from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        verification_link = f"{settings.verification_base_url}?token={token}"

        subject = "Verify your email address — Teamloom"
        body_html = f"""
        <html>
          <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
            <h2>Verify your email address</h2>
            <p>Hello {full_name},</p>
            <p>Thank you for signing up for Teamloom. Please click the button below to verify your email address and activate your account:</p>
            <div style="margin: 25px 0;">
              <a href="{verification_link}" style="background-color: #3FA88F; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Verify Email Address</a>
            </div>
            <p style="font-size: 13px; color: #666;">Or copy and paste this link into your browser:</p>
            <p style="font-size: 13px; color: #3FA88F; word-break: break-all;">{verification_link}</p>
            <p style="font-size: 12px; color: #999; margin-top: 30px;">This link will expire in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours. If you did not create a Teamloom account, please ignore this email.</p>
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
            logger.info("Verification email successfully sent via SMTP to %s", email)
            return True
        except Exception as e:
            logger.error("Failed to send verification email to %s: %s", email, e)
            return False

    def send_welcome_email(
        self, email: str, full_name: str, employee_code: str, temp_password: str
    ) -> bool:
        if not (settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_APP_PASSWORD):
            logger.warning("SMTP is not configured. Falling back to Console logger for welcome email.")
            return ConsoleEmailSender().send_welcome_email(email, full_name, employee_code, temp_password)

        from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        login_url = f"{settings.FRONTEND_URL}/login"

        subject = "Welcome to Teamloom — Account Created"
        body_html = f"""
        <html>
          <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
            <h2>Welcome to Teamloom</h2>
            <p>Hello {full_name},</p>
            <p>Your account has been created by your administrator.</p>
            <div style="background-color: #f4f6f8; padding: 15px; border-radius: 8px; margin: 15px 0;">
              <p><strong>User ID:</strong> {employee_code}</p>
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
            logger.info("Welcome email successfully sent to %s.", email)
            return True
        except Exception as e:
            logger.error("Failed to send welcome email to %s: %s", email, e)
            return False


class ConsoleEmailSender(EmailSender):
    """
    Console/Logger implementation of EmailSender.
    Used for local development, CI test suites, and deployments without external SMTP access.
    Prints the email verification link to standard server logs.
    """

    def send_verification_email(self, email: str, full_name: str, token: str) -> bool:
        verification_link = f"{settings.verification_base_url}?token={token}"
        logger.info(
            "[DEV EMAIL SENDER] Verification link for %s (%s): %s",
            email,
            full_name,
            verification_link,
        )
        return True

    def send_welcome_email(
        self, email: str, full_name: str, employee_code: str, temp_password: str
    ) -> bool:
        logger.info(
            "[DEV EMAIL SENDER] Welcome email for %s (%s), User ID: %s",
            email,
            full_name,
            employee_code,
        )
        return True


def get_email_sender() -> EmailSender:
    """Factory function returning the configured EmailSender instance (NFR-3)."""
    backend = settings.EMAIL_BACKEND.lower()
    if backend == "console":
        return ConsoleEmailSender()
    elif backend == "smtp":
        return SMTPEmailSender()
    else:  # "auto"
        if settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_APP_PASSWORD:
            return SMTPEmailSender()
        return ConsoleEmailSender()


def send_employee_welcome_email(
    email: str, full_name: str, employee_code: str, temp_password: str
) -> bool:
    """Backward-compatible helper invoking get_email_sender().send_welcome_email()."""
    return get_email_sender().send_welcome_email(
        email=email,
        full_name=full_name,
        employee_code=employee_code,
        temp_password=temp_password,
    )


def send_verification_email(email: str, full_name: str, token: str) -> bool:
    """Helper invoking get_email_sender().send_verification_email()."""
    return get_email_sender().send_verification_email(
        email=email,
        full_name=full_name,
        token=token,
    )
