import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, Notification, aware
from datetime import timezone


def audit(db: Session, club_id, actor_id, action: str, target: str | None = None, meta: dict | None = None):
    db.add(AuditLog(club_id=club_id, actor_id=actor_id, action=action, target=target, meta=meta or {}))


def notify(db: Session, user_id, title: str, body: str = "", link: str | None = None):
    db.add(Notification(user_id=user_id, title=title[:200], body=body, link=link))


def to_utc(dt):
    return None if dt is None else dt.astimezone(timezone.utc)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:50] or "event"


def unique_slug(db: Session, model, text: str) -> str:
    base = slugify(text)
    while True:
        slug = f"{base}-{secrets.token_hex(2)}"
        if not db.scalar(select(model.id).where(model.slug == slug)):
            return slug


def csv_safe(v) -> str:
    """Neutralize spreadsheet formula injection (=, +, -, @ at cell start)."""
    s = "" if v is None else (", ".join(map(str, v)) if isinstance(v, list) else str(v))
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def iso(dt):
    dt = aware(dt)
    return dt.isoformat() if dt else None


from datetime import timedelta  # noqa: E402

ONGOING_GRACE = timedelta(hours=3)   # an event with no end time counts as "ongoing" for 3 hours after it starts


def event_phase(e, now=None) -> str:
    from ..models import aware, utcnow
    now = now or utcnow()
    start = aware(e.starts_at)
    end = aware(e.ends_at) or start + ONGOING_GRACE
    return "upcoming" if now < start else ("ongoing" if now <= end else "past")
