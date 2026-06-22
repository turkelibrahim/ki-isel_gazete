"""SMTP HTML email service for event reminders."""

from __future__ import annotations

import html
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


class EmailService:
    """Send HTML emails through SMTP over SSL."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
    ) -> None:
        """Create an email service from explicit values or environment variables."""
        self.host = host if host is not None else os.getenv("SMTP_HOST", "")
        self.port = port if port is not None else int(os.getenv("SMTP_PORT", "465") or 465)
        self.username = username if username is not None else os.getenv("SMTP_USER", "")
        self.password = password if password is not None else os.getenv("SMTP_PASSWORD", "")
        self.from_email = from_email if from_email is not None else os.getenv("SMTP_FROM", self.username)

    def _is_configured(self) -> bool:
        """Return whether all required SMTP settings are present."""
        return bool(self.host and self.port and self.username and self.password and self.from_email)

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send an HTML email.

        Args:
            to_email: Recipient email address.
            subject: Email subject.
            html_body: HTML content for the message.

        Returns:
            ``True`` when SMTP delivery succeeds, otherwise ``False``.
        """
        if not to_email:
            logger.warning("Recipient email is missing; skipping email notification.")
            return False
        if not self._is_configured():
            logger.warning("SMTP configuration is incomplete; skipping email notification.")
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = to_email
        message.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL(self.host, self.port) as smtp:
                smtp.login(self.username, self.password)
                smtp.sendmail(self.from_email, [to_email], message.as_string())
            logger.info("HTML email sent successfully to %s.", to_email)
            return True
        except Exception:
            logger.exception("Failed to send HTML email to %s.", to_email)
            return False

    def build_event_reminder_html(self, user: Any, event: Any) -> str:
        """Build the standard event reminder HTML body."""
        event_title = html.escape(str(getattr(event, "title", "Etkinlik") or "Etkinlik"))
        event_description = html.escape(str(getattr(event, "description", "") or "Açıklama bulunmuyor."))
        event_category = html.escape(str(getattr(event, "category", "OTHER") or "OTHER"))
        event_date = getattr(event, "event_date", None)
        event_date_text = html.escape(event_date.isoformat() if hasattr(event_date, "isoformat") else str(event_date or "Tarih bilinmiyor"))
        user_name = html.escape(str(getattr(user, "email", "") or getattr(user, "id", "Kullanıcı") or "Kullanıcı"))

        return f"""
        <!doctype html>
        <html lang="tr">
          <head>
            <meta charset="utf-8" />
            <title>Etkinlik Hatırlatması</title>
          </head>
          <body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.5;">
            <div style="max-width: 640px; margin: 0 auto; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px;">
              <p style="font-size: 14px; color: #6b7280; margin: 0 0 12px;">Smart Personnel Newspaper System</p>
              <h1 style="font-size: 24px; margin: 0 0 12px;">Etkinlik Hatırlatması</h1>
              <p>Merhaba {user_name},</p>
              <p><strong>{event_title}</strong> etkinliği yaklaşıyor.</p>
              <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
                <tr><td style="padding: 8px; background: #f9fafb;">Başlık</td><td style="padding: 8px;">{event_title}</td></tr>
                <tr><td style="padding: 8px; background: #f9fafb;">Açıklama</td><td style="padding: 8px;">{event_description}</td></tr>
                <tr><td style="padding: 8px; background: #f9fafb;">Tarih</td><td style="padding: 8px;">{event_date_text}</td></tr>
                <tr><td style="padding: 8px; background: #f9fafb;">Kategori</td><td style="padding: 8px;">{event_category}</td></tr>
              </table>
              <p style="font-size: 13px; color: #6b7280; margin-top: 20px;">
                Bu hatırlatma kişisel gazete sistemindeki etkinlik takibinden gönderildi.
              </p>
            </div>
          </body>
        </html>
        """.strip()

    def send_event_reminder_email(self, user: Any, event: Any) -> bool:
        """Send a standard HTML event reminder email to a user."""
        to_email = getattr(user, "email", None) or ""
        event_title = getattr(event, "title", "Etkinlik") or "Etkinlik"
        subject = f"Etkinlik Hatırlatması: {event_title}"
        html_body = self.build_event_reminder_html(user=user, event=event)
        return self.send_email(to_email=to_email, subject=subject, html_body=html_body)
