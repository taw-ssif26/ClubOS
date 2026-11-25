import csv
import io
import secrets
from uuid import UUID
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import AwareDatetime, BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import segno

from ..config import settings
from ..db import get_db
from ..deps import ClubCtx, EventCtx, can_view_event, club_perm, current_user, current_user_optional, event_perm, get_membership
from ..models import Event, Registration, User, aware, utcnow
from ..services.plans import count_active_events, get_limits, lock_club, require_flag, require_room, uses_conditions
from ..services.reviews import rating_for
from ..permissions import has_perm
from ..ratelimit import rate_limit
from ..services.core import audit, csv_safe, event_phase, iso, notify, to_utc, unique_slug
from ..services.geo import location_out, resolve_location
from ..services.forms import FormError, validate_answers, validate_schema
from ..services.mail import queue_email

router = APIRouter(tags=["events"])


class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=10000)
    banner_url: HttpUrl | None = None
    venue: str = Field("", max_length=200)
    is_online: bool = False
    online_url: HttpUrl | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    capacity: int | None = Field(None, ge=1, le=100000)
    visibility: Literal["public", "members", "private"] = "public"
    status: Literal["draft", "published", "cancelled"] = "draft"
    registration_fields: list = []
    registration_closes_at: AwareDatetime | None = None
    location_mode: Literal["onsite", "online", "hybrid"] | None = None
    place: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None


class EventPatch(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=10000)
    banner_url: HttpUrl | None = None
    venue: str | None = Field(None, max_length=200)
    is_online: bool | None = None
    online_url: HttpUrl | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    capacity: int | None = Field(None, ge=1, le=100000)
    visibility: Literal["public", "members", "private"] | None = None
    status: Literal["draft", "published", "cancelled"] | None = None
    registration_fields: list | None = None
    registration_closes_at: AwareDatetime | None = None
    location_mode: Literal["onsite", "online", "hybrid"] | None = None
    place: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None


def _count(db: Session, event_id, status: str) -> int:
    return db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event_id, Registration.status == status))


def event_out(db: Session, e: Event, detail: bool = True) -> dict:
    d = {"rating": rating_for(db, f"event:{e.id}"), "slug": e.slug, "title": e.title, "description": e.description, "banner_url": e.banner_url, "venue": e.venue,
         "is_online": e.is_online, "starts_at": iso(e.starts_at), "ends_at": iso(e.ends_at), "capacity": e.capacity,
         "visibility": e.visibility, "status": e.status,
         "club": {"slug": e.club.slug, "name": e.club.name, "logo_url": e.club.logo_url},
         "registered": _count(db, e.id, "confirmed"), "registration_closes_at": iso(e.registration_closes_at),
         "phase": event_phase(e), "location": location_out(e)}
    if detail:
        d["registration_fields"] = e.registration_fields
    return d


def _apply_location(data: dict, cur: dict | None = None) -> None:
    keys = ("location_mode", "place", "address", "latitude", "longitude")
    if cur is None or any(k in data for k in keys):
        loc = resolve_location(data.pop("location_mode", None), data.pop("place", None), data.pop("address", None),
                               data.pop("latitude", None), data.pop("longitude", None), current=cur)
        data.update(loc)
        data["is_online"] = loc["location_mode"] in ("online", "hybrid")


def _clean_event_data(data: dict) -> dict:
    for k in ("banner_url", "online_url"):
        if data.get(k) is not None:
            data[k] = str(data[k])
    for k in ("starts_at", "ends_at", "registration_closes_at"):
        if k in data:
            data[k] = to_utc(data[k])
    if "registration_fields" in data and data["registration_fields"] is not None:
        try:
            data["registration_fields"] = validate_schema(data["registration_fields"])
        except FormError as ex:
            raise HTTPException(422, {"errors": ex.errors})
    if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
        raise HTTPException(422, "ends_at must be after starts_at")
    return data


@router.post("/clubs/{slug}/events", status_code=201)
def create_event(body: EventIn, ctx: ClubCtx = Depends(club_perm("events.manage")), db: Session = Depends(get_db)):
    data = _clean_event_data(body.model_dump())
    _apply_location(data)
    if uses_conditions(data["registration_fields"]):
        require_flag(db, ctx.club, "conditional_logic")
    lock_club(db, ctx.club.id)
    if data["status"] == "published":
        require_room(db, ctx.club, "active_events", count_active_events(db, ctx.club.id), "active events")
    e = Event(club_id=ctx.club.id, slug=unique_slug(db, Event, body.title), created_by=ctx.user.id, **data)
    db.add(e)
    db.flush()
    audit(db, ctx.club.id, ctx.user.id, "event.created", e.slug)
    db.commit()
    return event_out(db, e)


@router.get("/clubs/{slug}/events")
def club_events(include_past: bool = False, ctx: ClubCtx = Depends(club_perm("events.manage")), db: Session = Depends(get_db)):
    q = select(Event).where(Event.club_id == ctx.club.id)
    if not include_past:
        q = q.where(Event.starts_at >= utcnow() - timedelta(days=1))
    return [event_out(db, e, False) for e in db.scalars(q.order_by(Event.starts_at)).unique()]


@router.patch("/events/{slug}")
def update_event(body: EventPatch, ctx: EventCtx = Depends(event_perm("events.manage")), db: Session = Depends(get_db)):
    data = _clean_event_data(body.model_dump(exclude_unset=True))
    _apply_location(data, cur={"location_mode": ctx.event.location_mode, "place": ctx.event.place, "address": ctx.event.address,
                               "latitude": ctx.event.latitude, "longitude": ctx.event.longitude})
    if uses_conditions(data.get("registration_fields")):
        require_flag(db, ctx.club, "conditional_logic")
    if data.get("status") == "published" and ctx.event.status != "published":
        lock_club(db, ctx.club.id)
        require_room(db, ctx.club, "active_events", count_active_events(db, ctx.club.id, ctx.event.id), "active events")
    cancelled_now = data.get("status") == "cancelled" and ctx.event.status != "cancelled"
    for k, v in data.items():
        setattr(ctx.event, k, v)
    if cancelled_now:
        for r in db.scalars(select(Registration).where(Registration.event_id == ctx.event.id, Registration.status != "cancelled")).unique():
            notify(db, r.user_id, f"Event cancelled: {ctx.event.title}", link=f"/e/{ctx.event.slug}")
            queue_email(db, to=r.user.email, subject=f"Cancelled: {ctx.event.title}",
                        body=f"Hi {r.user.full_name.split()[0]},\n\n{ctx.event.title} has been cancelled by the organizers.\n", club_id=ctx.club.id)
    audit(db, ctx.club.id, ctx.user.id, "event.updated", ctx.event.slug, {"fields": sorted(data)})
    db.commit()
    return event_out(db, ctx.event)


@router.get("/events/{slug}")
def get_event(slug: str, user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    e = db.scalar(select(Event).where(Event.slug == slug))
    m = get_membership(db, e.club_id, user.id) if (e and user) else None
    if not e or not can_view_event(e, user, m):
        raise HTTPException(404, "Event not found")
    out = event_out(db, e)
    if user:
        r = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.user_id == user.id))
        out["my_registration"] = _reg_out(r) if r and r.status != "cancelled" else None
        # The join link of an online/hybrid event is for people who are actually in: confirmed registrants and organizers
        if e.online_url and ((r and r.status == "confirmed") or (m and m.status == "active" and has_perm(m, "events.manage"))):
            out["online_url"] = e.online_url
    return out


# ---- registration --------------------------------------------------------------------------

class RegisterIn(BaseModel):
    answers: dict = {}


def _reg_out(r: Registration) -> dict:
    return {"id": str(r.id), "status": r.status, "ticket_code": r.ticket_code, "checked_in_at": iso(r.checked_in_at)}


def waitlist_enabled(db: Session, club) -> bool:
    return bool(get_limits(db, club).get("waitlist"))


def _ticket() -> str:
    return "CLB-" + secrets.token_hex(5).upper()


@router.post("/events/{slug}/register", status_code=201, dependencies=[Depends(rate_limit("register-event", 40, 60))])
def register(slug: str, body: RegisterIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Row lock on the event serializes concurrent registrations, so capacity can't be oversold.
    e = db.scalar(select(Event).where(Event.slug == slug).with_for_update(of=Event))
    m = get_membership(db, e.club_id, user.id) if e else None
    if not e or not can_view_event(e, user, m) or e.status != "published":
        raise HTTPException(404, "Event not found")
    if not user.email_verified:
        raise HTTPException(403, "Verify your email first")
    deadline = aware(e.registration_closes_at) or aware(e.starts_at)
    if utcnow() >= deadline:
        raise HTTPException(409, "Registration is closed")
    try:
        answers = validate_answers(e.registration_fields, body.answers)
    except FormError as ex:
        raise HTTPException(422, {"errors": ex.errors})
    existing = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.user_id == user.id))
    if existing and existing.status != "cancelled":
        raise HTTPException(409, "You are already registered")
    confirmed = _count(db, e.id, "confirmed")
    if e.capacity is not None and confirmed >= e.capacity:
        if not waitlist_enabled(db, e.club):
            raise HTTPException(409, "This event is full")
        status = "waitlisted"
    else:
        status = "confirmed"
    if existing:  # re-registering after cancelling
        existing.status, existing.answers, existing.ticket_code, existing.checked_in_at = status, answers, _ticket(), None
        r = existing
    else:
        r = Registration(event_id=e.id, user_id=user.id, status=status, answers=answers, ticket_code=_ticket())
        db.add(r)
    word = "confirmed" if status == "confirmed" else "waitlisted"
    notify(db, user.id, f"Registration {word}: {e.title}", link=f"/e/{e.slug}")
    queue_email(db, to=user.email, subject=f"Registration {word}: {e.title}", club_id=e.club_id,
                body=f"Hi {user.full_name.split()[0]},\n\nYour registration for {e.title} is {word}.\n"
                     f"Registration ID: {r.ticket_code}\nTicket: {settings.base_url}/e/{e.slug}\n")
    db.commit()
    return _reg_out(r)


@router.delete("/events/{slug}/register")
def cancel_registration(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.scalar(select(Event).where(Event.slug == slug).with_for_update(of=Event))
    r = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.user_id == user.id)) if e else None
    if not r or r.status == "cancelled":
        raise HTTPException(404, "No active registration")
    was_confirmed = r.status == "confirmed"
    r.status = "cancelled"
    if was_confirmed:  # promote the earliest waitlisted person
        nxt = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.status == "waitlisted")
                        .order_by(Registration.created_at).limit(1))
        if nxt:
            nxt.status = "confirmed"
            notify(db, nxt.user_id, f"You're in! A spot opened for {e.title}", link=f"/e/{e.slug}")
            queue_email(db, to=nxt.user.email, subject=f"You're in: {e.title}", club_id=e.club_id,
                        body=f"A spot opened up and your registration for {e.title} is now confirmed.\nRegistration ID: {nxt.ticket_code}\n")
    db.commit()
    return {"ok": True}


@router.get("/registrations/{reg_id}/qr.svg")
def ticket_qr(reg_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(Registration).where(Registration.id == reg_id, Registration.user_id == user.id))
    if not r or r.status != "confirmed":
        raise HTTPException(404, "Ticket not found")
    buf = io.BytesIO()
    segno.make(r.ticket_code, error="m").save(buf, kind="svg", scale=8, border=2)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "private, no-store"})


# ---- participant management ----------------------------------------------------------------

def _reg_row(r: Registration) -> dict:
    return {**_reg_out(r), "user": {"username": r.user.username, "full_name": r.user.full_name, "email": r.user.email},
            "answers": r.answers, "registered_at": iso(r.created_at)}


@router.get("/events/{slug}/registrations")
def list_registrations(status: str | None = None, ctx: EventCtx = Depends(event_perm("registrations.manage")), db: Session = Depends(get_db)):
    q = select(Registration).where(Registration.event_id == ctx.event.id)
    if status:
        q = q.where(Registration.status == status)
    return [_reg_row(r) for r in db.scalars(q.order_by(Registration.created_at)).unique()]


@router.get("/events/{slug}/registrations.csv")
def export_registrations(ctx: EventCtx = Depends(event_perm("registrations.manage")), db: Session = Depends(get_db)):
    fields = ctx.event.registration_fields
    rows = db.scalars(select(Registration).where(Registration.event_id == ctx.event.id).order_by(Registration.created_at)).unique().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["registration_id", "status", "name", "email", "checked_in_at"] + [f["label"] for f in fields])
    for r in rows:
        w.writerow([csv_safe(x) for x in [r.ticket_code, r.status, r.user.full_name, r.user.email, iso(r.checked_in_at)]]
                   + [csv_safe(r.answers.get(f["id"])) for f in fields])
    audit(db, ctx.club.id, ctx.user.id, "event.registrations_exported", ctx.event.slug, {"rows": len(rows)})
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{ctx.event.slug}-registrations.csv"'})


# ---- check-in ------------------------------------------------------------------------------

class CheckInIn(BaseModel):
    ticket_code: str = Field(min_length=4, max_length=40)


@router.post("/events/{slug}/checkin")
def check_in(body: CheckInIn, ctx: EventCtx = Depends(event_perm("attendance.manage")), db: Session = Depends(get_db)):
    # Scoped to THIS event: a valid ticket for another event (or club) must not check in here.
    r = db.scalar(select(Registration).where(Registration.ticket_code == body.ticket_code.strip().upper(),
                                             Registration.event_id == ctx.event.id))
    if not r or r.status != "confirmed":
        raise HTTPException(404, "No confirmed registration for this ticket")
    if r.checked_in_at:
        raise HTTPException(409, {"message": "Already checked in", "checked_in_at": iso(r.checked_in_at), "name": r.user.full_name})
    r.checked_in_at, r.checked_in_by = utcnow(), ctx.user.id
    db.commit()
    return {"name": r.user.full_name, "checked_in_at": iso(r.checked_in_at)}


@router.post("/events/{slug}/checkin/manual/{reg_id}")
def manual_check_in(reg_id: UUID, ctx: EventCtx = Depends(event_perm("attendance.manage")), db: Session = Depends(get_db)):
    r = db.scalar(select(Registration).where(Registration.id == reg_id, Registration.event_id == ctx.event.id))
    if not r or r.status != "confirmed":
        raise HTTPException(404, "Registration not found")
    if r.checked_in_at:
        raise HTTPException(409, "Already checked in")
    r.checked_in_at, r.checked_in_by = utcnow(), ctx.user.id
    db.commit()
    return {"name": r.user.full_name, "checked_in_at": iso(r.checked_in_at)}


@router.get("/events/{slug}/attendance")
def attendance(ctx: EventCtx = Depends(event_perm("attendance.manage")), db: Session = Depends(get_db)):
    confirmed = _count(db, ctx.event.id, "confirmed")
    checked = db.scalar(select(func.count()).select_from(Registration).where(
        Registration.event_id == ctx.event.id, Registration.status == "confirmed", Registration.checked_in_at.is_not(None)))
    return {"confirmed": confirmed, "checked_in": checked, "waitlisted": _count(db, ctx.event.id, "waitlisted"),
            "attendance_rate": round(checked / confirmed, 3) if confirmed else None}
