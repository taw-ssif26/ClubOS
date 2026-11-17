from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, current_user_optional
from ..models import Membership, Notification, Registration, User, aware, utcnow

router = APIRouter(tags=["users"])


def user_out(u: User, private: bool = False) -> dict:
    d = {"id": str(u.id), "username": u.username, "full_name": u.full_name, "bio": u.bio, "avatar_url": u.avatar_url,
         "institution": u.institution, "department": u.department, "class_year": u.class_year,
         "skills": u.skills, "social_links": u.social_links}
    if private or u.show_email:
        d["email"] = u.email
    if private:
        d.update(email_verified=u.email_verified, profile_public=u.profile_public, show_email=u.show_email,
                 is_platform_admin=u.is_platform_admin, totp_enabled=u.totp_enabled)
    return d


class ProfileIn(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=120)
    bio: str | None = Field(None, max_length=1000)
    avatar_url: HttpUrl | None = None
    institution: str | None = Field(None, max_length=160)
    department: str | None = Field(None, max_length=120)
    class_year: str | None = Field(None, max_length=40)
    skills: list[str] | None = Field(None, max_length=30)
    social_links: dict[str, HttpUrl] | None = None
    profile_public: bool | None = None
    show_email: bool | None = None


@router.get("/users/me")
def me(user: User = Depends(current_user)):
    return user_out(user, private=True)


@router.patch("/users/me")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "avatar_url" in data and data["avatar_url"] is not None:
        data["avatar_url"] = str(data["avatar_url"])
    if "social_links" in data and data["social_links"] is not None:
        data["social_links"] = {k[:30]: str(v) for k, v in data["social_links"].items()}
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    return user_out(user, private=True)


@router.get("/users/me/memberships")
def my_memberships(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return [{"club": {"slug": m.club.slug, "name": m.club.name, "logo_url": m.club.logo_url},
             "role": m.role.name, "status": m.status, "joined_at": aware(m.joined_at).isoformat() if m.joined_at else None}
            for m in rows]


@router.get("/users/me/registrations")
def my_registrations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Registration).where(Registration.user_id == user.id, Registration.status != "cancelled")).all()
    return [{"id": str(r.id), "status": r.status, "ticket_code": r.ticket_code,
             "checked_in": r.checked_in_at is not None,
             "event": {"slug": r.event.slug, "title": r.event.title, "starts_at": aware(r.event.starts_at).isoformat()}}
            for r in sorted(rows, key=lambda r: aware(r.event.starts_at))]


@router.get("/users/{username}")
def public_profile(username: str, viewer: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
    if not u or (not u.profile_public and (not viewer or viewer.id != u.id)):
        raise HTTPException(404, "User not found")
    return user_out(u, private=bool(viewer and viewer.id == u.id))


# ---- notifications -------------------------------------------------------------------------

@router.get("/notifications")
def notifications(unread_only: bool = False, limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(q.order_by(Notification.created_at.desc()).limit(min(limit, 100))).all()
    return [{"id": str(n.id), "title": n.title, "body": n.body, "link": n.link, "read": n.read_at is not None,
             "created_at": aware(n.created_at).isoformat()} for n in rows]


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))):
        n.read_at = utcnow()
    db.commit()
    return {"ok": True}


@router.post("/notifications/{nid}/read")
def read_one(nid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(Notification).where(Notification.id == nid, Notification.user_id == user.id))
    if not n:
        raise HTTPException(404, "Notification not found")
    n.read_at = n.read_at or utcnow()
    db.commit()
    return {"ok": True}
