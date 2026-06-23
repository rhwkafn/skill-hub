"""
Email Sender - A utility for sending emails via SMTP.

Supports:
- Sending to multiple recipients (To, CC, BCC)
- HTML and plain text bodies
- File attachments
- TLS/SSL encryption
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from email.utils import formataddr, formatdate
from typing import List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EmailConfig:
    """SMTP server configuration."""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False


@dataclass
class EmailMessage:
    """Email message structure."""
    sender: str
    recipients: List[str]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    attachments: List[Union[str, Path]] = field(default_factory=list)
    reply_to: Optional[str] = None


class EmailSender:
    """Handles sending emails through an SMTP server."""

    def __init__(self, config: EmailConfig):
        self.config = config
        self._connection: Optional[smtplib.SMTP] = None

    def connect(self) -> None:
        """Establish connection to the SMTP server."""
        if self.config.use_ssl:
            self._connection = smtplib.SMTP_SSL(
                self.config.smtp_server, self.config.smtp_port
            )
        else:
            self._connection = smtplib.SMTP(
                self.config.smtp_server, self.config.smtp_port
            )
            if self.config.use_tls:
                self._connection.starttls()

        self._connection.login(self.config.username, self.config.password)

    def disconnect(self) -> None:
        """Close the SMTP connection."""
        if self._connection:
            try:
                self._connection.quit()
            except smtplib.SMTPException:
                self._connection.close()
            finally:
                self._connection = None

    def _build_message(self, email: EmailMessage) -> MIMEMultipart:
        """Build a MIME message from an EmailMessage object."""
        msg = MIMEMultipart("mixed")
        msg["From"] = email.sender
        msg["To"] = ", ".join(email.recipients)
        msg["Subject"] = email.subject
        msg["Date"] = formatdate(localtime=True)

        if email.cc:
            msg["Cc"] = ", ".join(email.cc)
        if email.reply_to:
            msg["Reply-To"] = email.reply_to

        # Build the body part
        if email.body_html and email.body_text:
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(email.body_text, "plain", "utf-8"))
            body_part.attach(MIMEText(email.body_html, "html", "utf-8"))
        elif email.body_html:
            body_part = MIMEText(email.body_html, "html", "utf-8")
        else:
            body_part = MIMEText(email.body_text or "", "plain", "utf-8")

        msg.attach(body_part)

        # Attach files
        for attachment_path in email.attachments:
            path = Path(attachment_path)
            if not path.exists():
                raise FileNotFoundError(f"Attachment not found: {path}")

            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())

            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={path.name}",
            )
            msg.attach(part)

        return msg

    def _get_all_recipients(self, email: EmailMessage) -> List[str]:
        """Get the complete list of all recipients (To + CC + BCC)."""
        return email.recipients + email.cc + email.bcc

    def send(self, email: EmailMessage) -> None:
        """Send a single email message.

        Args:
            email: The EmailMessage to send.

        Raises:
            smtplib.SMTPException: If sending fails.
            FileNotFoundError: If an attachment does not exist.
        """
        if not self._connection:
            self.connect()

        msg = self._build_message(email)
        all_recipients = self._get_all_recipients(email)
        self._connection.sendmail(email.sender, all_recipients, msg.as_string())

    def send_batch(self, emails: List[EmailMessage]) -> dict:
        """Send multiple emails and report results.

        Args:
            emails: List of EmailMessage objects to send.

        Returns:
            Dict with 'sent' (list of indices) and 'failed' (list of (index, error)).
        """
        results = {"sent": [], "failed": []}

        if not self._connection:
            self.connect()

        for i, email in enumerate(emails):
            try:
                self.send(email)
                results["sent"].append(i)
            except Exception as e:
                results["failed"].append((i, str(e)))

        return results

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False


def create_message(
    sender: str,
    to: Union[str, List[str]],
    subject: str,
    body: str = "",
    html: bool = False,
    cc: Optional[Union[str, List[str]]] = None,
    bcc: Optional[Union[str, List[str]]] = None,
    attachments: Optional[List[Union[str, Path]]] = None,
    reply_to: Optional[str] = None,
) -> EmailMessage:
    """Convenience function to create an EmailMessage.

    Args:
        sender: Sender email address.
        to: Recipient(s) - single string or list.
        subject: Email subject line.
        body: Email body content.
        html: If True, body is treated as HTML; otherwise plain text.
        cc: Carbon copy recipient(s).
        bcc: Blind carbon copy recipient(s).
        attachments: List of file paths to attach.
        reply_to: Reply-to address (defaults to sender).

    Returns:
        Configured EmailMessage instance.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    cc_list = [] if cc is None else ([cc] if isinstance(cc, str) else list(cc))
    bcc_list = [] if bcc is None else ([bcc] if isinstance(bcc, str) else list(bcc))

    return EmailMessage(
        sender=sender,
        recipients=recipients,
        subject=subject,
        body_html=body if html else None,
        body_text=None if html else body,
        cc=cc_list,
        bcc=bcc_list,
        attachments=attachments or [],
        reply_to=reply_to,
    )


# ---------------------------------------------------------------------------
# Example / Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Example usage (will not actually send without valid credentials)
    config = EmailConfig(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        username="your_email@gmail.com",
        password="your_app_password",
        use_tls=True,
    )

    # Simple plain text email
    msg = create_message(
        sender="your_email@gmail.com",
        to=["recipient1@example.com", "recipient2@example.com"],
        subject="Hello from EmailSender",
        body="This is a plain text email sent via the EmailSender utility.",
        cc="cc_recipient@example.com",
    )

    # HTML email with attachment
    html_msg = create_message(
        sender="your_email@gmail.com",
        to="recipient@example.com",
        subject="HTML Email with Attachment",
        body="""
        <html>
        <body>
            <h1>Hello!</h1>
            <p>This is an <b>HTML email</b> with an attachment.</p>
        </body>
        </html>
        """,
        html=True,
        attachments=["report.pdf"],
    )

    # Send using context manager
    with EmailSender(config) as sender:
        results = sender.send_batch([msg, html_msg])
        print(f"Sent: {len(results['sent'])}, Failed: {len(results['failed'])}")
        for idx, error in results["failed"]:
            print(f"  Email {idx} failed: {error}")
