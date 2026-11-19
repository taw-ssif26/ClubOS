from uuid import UUID
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ClubCtx, club_perm
from ..models import EmailOptOut, EmailOutbox, Event, Membership, Registration, utcnow
from .account import unsubscribe_url
from ..services.plans import get_limits, require_flag
from ..services.core import audit, iso, to_utc
from ..services.mail import queue_email, render, template_vars

router = APIRouter(prefix="/clubs/{slug}/communications", tags=["communications"])
ALLOWED_VARS = {"first_name", "full_name", "club_name", "event_name"}


class Audience(BaseModel):
    type: Literal["all_members", "role", "event_registered", "event_checked_in", "event_not_checked_in"]
    role_id: UUID | None = None
    event_slug: str | None = None


class SendIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    audience: Audience
    send_at: AwareDatetime | None = None


def resolve_audience(db: Session, club, aud: Audience):
    """Returns (list of Users, event or None). Always scoped to the sender's club."""
    event = None
    if aud.type in ("all_members", "role"):
        q = select(Membership).where(Membership.club_id == club.id, Membership.status == "active")
        if aud.type == "role":
            if not aud.role_id:
                raise HTTPException(422, "role_id is required")
            q = q.where(Membership.role_id == aud.role_id)
        return [m.user for m in db.scalars(q).unique()], None
    event = db.scalar(select(Event).where(Event.slug == (aud.event_slug or ""), Event.club_id == club.id))
    if not event:
        raise HTTPException(404, "Event not found in this club")
    q = select(Registration).where(Registration.event_id == event.id, Registration.status == "confirmed")
    if aud.type == "event_checked_in":
        q = q.where(Registration.checked_in_at.is_not(None))
    if aud.type == "event_not_checked_in":
        q = q.where(Registration.checked_in_at.is_(None))
    return [r.user for r in db.scalars(q).unique()], event


@router.post("", status_code=201)
def send(body: SendIn, ctx: ClubCtx = Depends(club_perm("comms.send")), db: Session = Depends(get_db)):
    require_flag(db, ctx.club, "bulk_email")
    unknown = (template_vars(body.subject) | template_vars(body.body)) - ALLOWED_VARS
    if unknown:
        raise HTTPException(422, f"Unknown template variables: {sorted(unknown)}. Allowed: {sorted(ALLOWED_VARS)}")
    users, event = resolve_audience(db, ctx.club, body.audience)
    opted_out = set(db.scalars(select(EmailOptOut.user_id).where(EmailOptOut.club_id == ctx.club.id)))
    skipped = len([u for u in users if u.id in opted_out])
    users = [u for u in users if u.id not in opted_out]  # honour unsubscribes, always
    if not users:
        raise HTTPException(422, "Audience is empty")
    sent_today = db.scalar(select(func.count()).select_from(EmailOutbox).where(
        EmailOutbox.club_id == ctx.club.id, EmailOutbox.created_at >= utcnow() - timedelta(days=1)))
    limit = get_limits(db, ctx.club).get("emails_per_day") or 0
    if sent_today + len(users) > limit:
        raise HTTPException(402, f"Daily email limit reached ({limit} on your plan; {sent_today} used)")
    send_at = to_utc(body.send_at)
    for u in users:
        ctxvars = {"first_name": u.full_name.split()[0], "full_name": u.full_name, "club_name": ctx.club.name,
                   "event_name": event.title if event else ""}
        link = unsubscribe_url(u.id, ctx.club.id)
        footer = f"\n\n--\nYou're receiving this because you're part of {ctx.club.name} on ClubOS.\nUnsubscribe from {ctx.club.name} emails: {link}\n"
        row = queue_email(db, to=u.email, subject=render(body.subject, ctxvars), body=render(body.body, ctxvars) + footer,
                          club_id=ctx.club.id, send_at=send_at)
        row.unsubscribe_url, row.priority = link, 10
    audit(db, ctx.club.id, ctx.user.id, "communication.sent", body.subject[:80], {"recipients": len(users)})
    db.commit()
    return {"queued": len(users), "skipped_unsubscribed": skipped, "send_at": iso(send_at)}


@router.get("")
def history(ctx: ClubCtx = Depends(club_perm("comms.send")), db: Session = Depends(get_db)):
    rows = db.execute(select(EmailOutbox.subject, EmailOutbox.status, func.count()).where(EmailOutbox.club_id == ctx.club.id)
                      .group_by(EmailOutbox.subject, EmailOutbox.status)).all()
    return [{"subject": s, "status": st, "count": n} for s, st, n in rows]
