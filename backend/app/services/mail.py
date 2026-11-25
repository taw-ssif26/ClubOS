import logging
import re
import smtplib

import httpx
from datetime import timedelta
from email.message import EmailMessage
from email.utils import parseaddr

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import EmailOutbox, utcnow

log = logging.getLogger("clubos.mail")
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
MAX_ATTEMPTS = 5


def template_vars(template: str) -> set[str]:
    return set(VAR_RE.findall(template))


def render(template: str, ctx: dict) -> str:
    return VAR_RE.sub(lambda m: str(ctx.get(m.group(1), "")), template)


def queue_email(db: Session, *, to: str, subject: str, body: str, club_id=None, send_at=None) -> EmailOutbox:
    row = EmailOutbox(to_email=to, subject=" ".join(subject.split())[:300], body=body, club_id=club_id, send_at=send_at)
    db.add(row)
    return row


class ConsoleSender:
    def send(self, to: str, subject: str, body: str, unsubscribe_url: str | None = None) -> None:
        log.info("EMAIL to=%s subject=%s\n%s", to, subject, body)


class SmtpSender:
    def send(self, to: str, subject: str, body: str, unsubscribe_url: str | None = None) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
        if unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)


class BrevoSender:
    """Brevo transactional API (POST /v3/smtp/email): works on hosts that block outbound SMTP.
    The From address (SMTP_FROM) must be a verified sender in your Brevo account."""
    URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=20)

    def send(self, to: str, subject: str, body: str, unsubscribe_url: str | None = None) -> None:
        name, addr = parseaddr(settings.smtp_from)
        payload = {"sender": {"email": addr, **({"name": name} if name else {})}, "to": [{"email": to}], "subject": subject, "textContent": body}
        if unsubscribe_url:
            payload["headers"] = {"List-Unsubscribe": f"<{unsubscribe_url}>"}
        r = self.client.post(self.URL, json=payload, headers={"api-key": settings.brevo_api_key, "accept": "application/json"})
        if r.status_code >= 300:
            raise RuntimeError(f"brevo {r.status_code}: {r.text[:200]}")


def get_sender():
    if settings.brevo_api_key:
        return BrevoSender()
    return SmtpSender() if settings.smtp_host else ConsoleSender()


def process_outbox(db: Session, sender, batch: int = 50) -> tuple[int, int]:
    """Send due emails. Retries with exponential backoff, gives up after MAX_ATTEMPTS."""
    now = utcnow()
    if settings.email_daily_cap:  # provider limit (e.g. Brevo free 300/day): the rest simply waits for tomorrow
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = db.scalar(select(func.count()).select_from(EmailOutbox).where(EmailOutbox.status == "sent", EmailOutbox.sent_at >= day_start))
        room = settings.email_daily_cap - sent_today
        if room <= 0:
            return 0, 0
        batch = min(batch, room)
    rows = db.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.status == "pending", or_(EmailOutbox.send_at.is_(None), EmailOutbox.send_at <= now))
        .order_by(EmailOutbox.priority, EmailOutbox.created_at)  # verification mail never waits behind a campaign
        .limit(batch)
        .with_for_update(skip_locked=True)
    ).all()
    sent = failed = 0
    for row in rows:
        row.attempts += 1
        try:
            sender.send(row.to_email, row.subject, row.body, row.unsubscribe_url)
            row.status, row.sent_at, row.error = "sent", utcnow(), None
            sent += 1
        except Exception as e:  # noqa: BLE001 - any transport failure is retryable
            row.error = str(e)[:500]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
                failed += 1
            else:
                row.send_at = utcnow() + timedelta(minutes=2 ** row.attempts)
        db.commit()
    return sent, failed
