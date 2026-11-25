"""Retention: keep the database small and keep personal data only as long as it's useful."""
from datetime import timedelta

from sqlalchemy import and_, delete, or_
from sqlalchemy.orm import Session

from ..models import EmailOutbox, EmailToken, LoginEvent, Notification, Session as UserSession, utcnow


def purge(db: Session) -> dict:
    now = utcnow()
    out = {}
    def run(name, stmt):
        out[name] = db.execute(stmt).rowcount
    run("emails_sent", delete(EmailOutbox).where(EmailOutbox.status == "sent", EmailOutbox.sent_at < now - timedelta(days=30)))
    run("emails_failed", delete(EmailOutbox).where(EmailOutbox.status == "failed", EmailOutbox.created_at < now - timedelta(days=90)))
    run("sessions", delete(UserSession).where(or_(UserSession.expires_at < now - timedelta(days=7), and_(UserSession.revoked.is_(True), UserSession.created_at < now - timedelta(days=30)))))
    run("email_tokens", delete(EmailToken).where(or_(EmailToken.expires_at < now - timedelta(days=7), and_(EmailToken.used.is_(True), EmailToken.created_at < now - timedelta(days=7)))))
    run("login_events", delete(LoginEvent).where(LoginEvent.created_at < now - timedelta(days=90)))
    run("notifications", delete(Notification).where(Notification.read_at.is_not(None), Notification.read_at < now - timedelta(days=180)))
    db.commit()
    return out
