import aiosmtplib
from email.message import EmailMessage
from app.core.config import settings

async def send_email(subject: str, email_to: str, body: str):
    """
    Sends an email asynchronously using SMTP.
    """
    message = EmailMessage()
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = email_to
    message["Subject"] = subject
    message.set_content(body)

    # In Dev/Test, if no config provided, just print
    if settings.SMTP_HOST == "localhost":
        print(f"--- [EMAIL SENT] To: {email_to} | Subject: {subject} ---\n{body}")
        return

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )