from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Club, Event, Institution, Membership, Session as UserSession, User, aware, utcnow
from .permissions import has_perm
from .security import token_hash

COOKIE = "clubos_session"


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE)
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        return None
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token), UserSession.revoked.is_(False)))
    if not sess or aware(sess.expires_at) < utcnow():
        return None
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        return None
    request.state.session_id = sess.id
    return user


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def verified_user(user: User = Depends(current_user)) -> User:
    if not user.email_verified:
        raise HTTPException(403, "Verify your email first")
    return user


def platform_admin(user: User = Depends(current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(403, "Platform admin only")
    if settings.require_admin_2fa and not user.totp_enabled:
        raise HTTPException(403, {"code": "admin_2fa_required", "message": "Enable two-factor authentication in your security settings to use the admin area"})
    return user


def get_membership(db: Session, club_id, user_id) -> Membership | None:
    if not user_id:
        return None
    return db.scalar(select(Membership).where(Membership.club_id == club_id, Membership.user_id == user_id))


def is_institution_member(db: Session, institution: Institution | None, user: User | None) -> bool:
    if not institution or not user or not user.email_verified or not institution.email_domain:
        return False
    return user.email.endswith("@" + institution.email_domain.lower())


def can_view_club(db: Session, club: Club, user: User | None, m: Membership | None) -> bool:
    if m and m.status in ("active", "pending", "invited"):
        return True
    if club.visibility in ("public", "unlisted"):
        return True
    if club.visibility == "institution":
        return is_institution_member(db, club.institution, user)
    return False


def get_club_or_404(db: Session, slug: str) -> Club:
    club = db.scalar(select(Club).where(Club.slug == slug))
    if not club:
        raise HTTPException(404, "Club not found")
    return club


@dataclass
class ClubCtx:
    club: Club
    membership: Membership
    user: User


def club_perm(perm: str | None):
    """Dependency: caller must be an ACTIVE member of the club holding `perm`.
    Non-members get 404 so private clubs are not discoverable."""
    def dep(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ClubCtx:
        club = get_club_or_404(db, slug)
        m = get_membership(db, club.id, user.id)
        if not m or m.status != "active":
            raise HTTPException(404, "Club not found")
        if perm and not has_perm(m, perm):
            raise HTTPException(403, f"Missing permission: {perm}")
        return ClubCtx(club, m, user)
    return dep


@dataclass
class EventCtx:
    event: Event
    club: Club
    membership: Membership
    user: User


def event_perm(perm: str):
    """Dependency for /events/{slug}/... management endpoints. Authorization is
    always evaluated against the club that OWNS the event (object-level check)."""
    def dep(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> EventCtx:
        event = db.scalar(select(Event).where(Event.slug == slug))
        if not event:
            raise HTTPException(404, "Event not found")
        m = get_membership(db, event.club_id, user.id)
        if not m or m.status != "active":
            raise HTTPException(404, "Event not found")
        if not has_perm(m, perm):
            raise HTTPException(403, f"Missing permission: {perm}")
        return EventCtx(event, event.club, m, user)
    return dep


def can_view_event(event: Event, user: User | None, m: Membership | None) -> bool:
    if m and m.status == "active" and has_perm(m, "events.manage"):
        return True
    if event.status == "draft":
        return False
    if event.visibility == "public":
        return True
    if event.visibility == "members":
        return bool(m and m.status == "active")
    return False
