"""Plan limits and feature flags. Limits live in the DB (editable from super admin); None = unlimited."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Club, Event, Membership, Plan, Role, Upload, aware, utcnow
from ..permissions import ADMIN_RANK
from ..seed import DEFAULT_PLANS

FLAG_MESSAGES = {
    "bulk_email": "Bulk and scheduled email is a Pro feature.",
    "conditional_logic": "Conditional form logic is a Pro feature.",
    "waitlist": "Waitlists are a Pro feature. This event is full.",
    "advanced_themes": "This theme option is part of Pro.",
    "advanced_analytics": "Advanced analytics is a Pro feature.",
    "remove_branding": "Reduced branding is a Pro feature.",
}
_FREE = next(p for p in DEFAULT_PLANS if p["key"] == "free")["limits"]


def effective_plan_key(club: Club) -> str:
    exp = aware(club.plan_expires_at)
    return "free" if club.plan != "free" and exp and exp < utcnow() else club.plan


def get_limits(db: Session, club: Club) -> dict:
    key = effective_plan_key(club)
    plan = db.scalar(select(Plan).where(Plan.key == key))
    return plan.limits if plan else _FREE


def require_flag(db: Session, club: Club, flag: str):
    if not get_limits(db, club).get(flag):
        raise HTTPException(402, {"code": "upgrade_required", "feature": flag, "message": FLAG_MESSAGES[flag]})


def require_room(db: Session, club: Club, name: str, current: int, label: str):
    lim = get_limits(db, club).get(name)
    if lim is not None and current >= lim:
        raise HTTPException(402, {"code": "limit_reached", "limit": name, "max": lim,
                                  "message": f"Your plan allows up to {lim} {label}. Upgrade to add more."})


def count_members(db: Session, club_id) -> int:
    return db.scalar(select(func.count()).select_from(Membership).where(Membership.club_id == club_id, Membership.status == "active"))


def count_admins(db: Session, club_id) -> int:
    return db.scalar(select(func.count()).select_from(Membership).join(Role, Role.id == Membership.role_id)
                     .where(Membership.club_id == club_id, Membership.status == "active", Role.rank >= ADMIN_RANK))


def count_active_events(db: Session, club_id, exclude_id=None) -> int:
    q = select(func.count()).select_from(Event).where(Event.club_id == club_id, Event.status == "published",
                                                      func.coalesce(Event.ends_at, Event.starts_at) >= utcnow())
    if exclude_id:
        q = q.where(Event.id != exclude_id)
    return db.scalar(q)


def storage_used(db: Session, club_id) -> int:
    return db.scalar(select(func.coalesce(func.sum(Upload.size), 0)).where(Upload.club_id == club_id))


def uses_conditions(fields: list) -> bool:
    return any(isinstance(x, dict) and x.get("show_if") for x in (fields or []))


def usage(db: Session, club: Club) -> dict:
    lim = get_limits(db, club)
    return {"plan": club.plan, "effective_plan": effective_plan_key(club), "expires_at": club.plan_expires_at and aware(club.plan_expires_at).isoformat(),
            "limits": lim,
            "usage": {"members": count_members(db, club.id), "admins": count_admins(db, club.id),
                      "active_events": count_active_events(db, club.id), "storage_bytes": storage_used(db, club.id)}}


def branding_visible(db: Session, club: Club) -> bool:
    """ClubOS branding is required on Free; Pro can hide it."""
    return not (club.theme.get("hide_branding") and get_limits(db, club).get("remove_branding"))


def lock_club(db: Session, club_id) -> None:
    """Serialize limit checks per club (members / admin seats / active events) so concurrent requests can't overshoot."""
    db.execute(select(Club.id).where(Club.id == club_id).with_for_update())
