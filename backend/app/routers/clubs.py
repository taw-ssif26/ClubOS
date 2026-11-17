import re
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (ClubCtx, club_perm, current_user, current_user_optional, can_view_club, get_club_or_404,
                    get_membership, verified_user)
from ..models import AuditLog, Club, Event, Institution, Membership, Registration, Role, User, aware, utcnow
from ..permissions import ADMIN_RANK, DEFAULT_ROLES, PERMS, has_perm
from ..services.plans import (lock_club, branding_visible, count_admins, count_members, require_flag, require_room, uses_conditions)
from ..services.core import audit, iso, notify
from ..services.forms import FormError, validate_answers, validate_schema
from ..services.mail import queue_email
from ..config import settings
from ..ratelimit import rate_limit
from ..services.reviews import rating_for

router = APIRouter(prefix="/clubs", tags=["clubs"])
SLUG_RE = r"^[a-z0-9][a-z0-9-]{2,39}$"
RESERVED = {"admin", "api", "new", "settings", "discover", "events", "clubs", "login", "register", "verify", "c", "e"}
FREE_PRESETS = {"minimal", "editorial", "academic"}
THEME_PRESETS = FREE_PRESETS | {"modern", "bold", "professional"}
FONTS = {"display-serif", "grotesk", "humanist", "mono"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
CATEGORIES = {"general", "technology", "science", "arts", "culture", "sports", "business", "debate", "social", "academic", "media"}


def club_out(c: Club, m: Membership | None = None, rating: dict | None = None, branding: bool = True) -> dict:
    return {"id": str(c.id), "slug": c.slug, "name": c.name, "description": c.description, "category": c.category,
            "logo_url": c.logo_url, "cover_url": c.cover_url, "contact_email": c.contact_email,
            "social_links": c.social_links, "visibility": c.visibility, "join_policy": c.join_policy,
            "theme": c.theme, "verified": c.verified, "plan": c.plan, "rating": rating, "show_branding": branding,
            "institution": {"slug": c.institution.slug, "name": c.institution.name} if c.institution else None,
            "application_fields": c.application_fields,
            "my_membership": {"status": m.status, "role": m.role.name,
                              "permissions": m.role.permissions} if m else None}


def validate_theme(theme: dict, db: Session, club: Club) -> dict:
    """Constrained on purpose (presets + 3 colors + font) so clubs can't build ugly sites.
    Free: 3 presets + primary color. Pro: all presets, all colors, typography, reduced branding."""
    out = {}
    advanced = False
    if "preset" in theme:
        if theme["preset"] not in THEME_PRESETS:
            raise HTTPException(422, f"preset must be one of {sorted(THEME_PRESETS)}")
        advanced |= theme["preset"] not in FREE_PRESETS
        out["preset"] = theme["preset"]
    for k in ("primary", "secondary", "accent"):
        if k in theme:
            if not isinstance(theme[k], str) or not HEX.match(theme[k]):
                raise HTTPException(422, f"theme.{k} must be a #RRGGBB color")
            advanced |= k != "primary"
            out[k] = theme[k]
    if "font" in theme:
        if theme["font"] not in FONTS:
            raise HTTPException(422, f"font must be one of {sorted(FONTS)}")
        advanced = True
        out["font"] = theme["font"]
    if advanced:
        require_flag(db, club, "advanced_themes")
    if "hide_branding" in theme:
        if theme["hide_branding"]:
            require_flag(db, club, "remove_branding")
        out["hide_branding"] = bool(theme["hide_branding"])
    return out


class ClubCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=SLUG_RE)
    description: str = Field("", max_length=3000)
    category: str = "general"
    institution_slug: str | None = None
    visibility: Literal["public", "private", "institution", "unlisted"] = "public"
    join_policy: Literal["open", "request", "invite"] = "request"


class ClubUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=3000)
    category: str | None = None
    logo_url: str | None = Field(None, max_length=500, pattern=r"^(https?://[^\s\"'()<>\\]+|/media/[A-Za-z0-9-]+/[A-Za-z0-9]+\.(png|jpg|webp))$")
    cover_url: str | None = Field(None, max_length=500, pattern=r"^(https?://[^\s\"'()<>\\]+|/media/[A-Za-z0-9-]+/[A-Za-z0-9]+\.(png|jpg|webp))$")
    contact_email: EmailStr | None = None
    social_links: dict[str, HttpUrl] | None = None
    visibility: Literal["public", "private", "institution", "unlisted"] | None = None
    join_policy: Literal["open", "request", "invite"] | None = None
    theme: dict | None = None
    application_fields: list | None = None


@router.post("", status_code=201)
def create_club(body: ClubCreate, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    if body.slug in RESERVED:
        raise HTTPException(422, "That slug is reserved")
    if body.category not in CATEGORIES:
        raise HTTPException(422, f"category must be one of {sorted(CATEGORIES)}")
    if db.scalar(select(Club.id).where(Club.slug == body.slug)):
        raise HTTPException(409, "Slug already taken")
    inst = None
    if body.institution_slug:
        inst = db.scalar(select(Institution).where(Institution.slug == body.institution_slug))
        if not inst:
            raise HTTPException(404, "Institution not found")
    if body.visibility == "institution" and not inst:
        raise HTTPException(422, "institution visibility requires an institution")
    club = Club(name=body.name.strip(), slug=body.slug, description=body.description, category=body.category,
                institution_id=inst.id if inst else None, visibility=body.visibility,
                join_policy=body.join_policy, created_by=user.id, theme={"preset": "minimal"})
    db.add(club)
    db.flush()
    roles = {}
    for name, perms, rank in DEFAULT_ROLES:
        r = Role(club_id=club.id, name=name, permissions=perms, rank=rank, is_system=True)
        db.add(r)
        roles[name] = r
    db.flush()
    m = Membership(club_id=club.id, user_id=user.id, role_id=roles["Owner"].id, status="active", joined_at=utcnow())
    db.add(m)
    audit(db, club.id, user.id, "club.created", club.slug)
    db.commit()
    return club_out(club, m)


@router.get("/{slug}")
def get_club(slug: str, user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    m = get_membership(db, club.id, user.id if user else None)
    if not can_view_club(db, club, user, m):
        raise HTTPException(404, "Club not found")
    return club_out(club, m, rating_for(db, f"club:{club.id}"), branding_visible(db, club))


@router.patch("/{slug}")
def update_club(body: ClubUpdate, ctx: ClubCtx = Depends(club_perm("club.settings")), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "category" in data and data["category"] not in CATEGORIES:
        raise HTTPException(422, f"category must be one of {sorted(CATEGORIES)}")
    if data.get("visibility") == "institution" and not ctx.club.institution_id:
        raise HTTPException(422, "institution visibility requires an institution")
    if "theme" in data and data["theme"] is not None:
        data["theme"] = {**ctx.club.theme, **validate_theme(data["theme"], db, ctx.club)}
    if "application_fields" in data and data["application_fields"] is not None:
        try:
            data["application_fields"] = validate_schema(data["application_fields"])
        except FormError as e:
            raise HTTPException(422, {"errors": e.errors})
        if uses_conditions(data["application_fields"]):
            require_flag(db, ctx.club, "conditional_logic")
    if "social_links" in data and data["social_links"] is not None:
        data["social_links"] = {k[:30]: str(v) for k, v in data["social_links"].items()}
    for k, v in data.items():
        setattr(ctx.club, k, v)
    audit(db, ctx.club.id, ctx.user.id, "club.updated", ctx.club.slug, {"fields": sorted(data)})
    db.commit()
    return club_out(ctx.club, ctx.membership, rating_for(db, f"club:{ctx.club.id}"), branding_visible(db, ctx.club))


# ---- joining -------------------------------------------------------------------------------

class JoinIn(BaseModel):
    application: dict = {}


def _active_count(db: Session, club_id) -> int:
    return count_members(db, club_id)


def _check_member_limit(db: Session, club: Club):
    require_room(db, club, "members", _active_count(db, club.id), "members")


def _role(db: Session, club_id, name: str) -> Role:
    return db.scalar(select(Role).where(Role.club_id == club_id, Role.name == name))


@router.post("/{slug}/join", dependencies=[Depends(rate_limit("join", 30, 60))])
def join(slug: str, body: JoinIn, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    m = get_membership(db, club.id, user.id)
    if not can_view_club(db, club, user, m):
        raise HTTPException(404, "Club not found")
    if m and m.status in ("active", "pending"):
        raise HTTPException(409, f"Already {m.status}")
    if m and m.status in ("rejected", "suspended"):
        raise HTTPException(403, f"Your membership is {m.status}. Contact the club.")
    if club.join_policy == "invite" and not (m and m.status == "invited"):
        raise HTTPException(403, "This club is invitation only")
    try:
        answers = validate_answers(club.application_fields, body.application) if club.application_fields else {}
    except FormError as e:
        raise HTTPException(422, {"errors": e.errors})
    lock_club(db, club.id)
    member_role = _role(db, club.id, "Member")
    if club.join_policy == "open" or (m and m.status == "invited"):
        _check_member_limit(db, club)
        status = "active"
    else:
        status = "pending"
    if m:  # former / invited
        m.status, m.application = status, answers
    else:
        m = Membership(club_id=club.id, user_id=user.id, role_id=member_role.id, status=status, application=answers)
        db.add(m)
    if status == "active":
        m.joined_at = utcnow()
    else:
        for owner in db.scalars(select(Membership).where(Membership.club_id == club.id, Membership.status == "active")):
            if has_perm(owner, "members.manage"):
                notify(db, owner.user_id, f"New membership request: {user.full_name}", club.name, f"/clubs/{club.slug}/members")
    audit(db, club.id, user.id, "member.joined" if status == "active" else "member.applied", user.username)
    db.commit()
    return {"status": status}


# ---- members -------------------------------------------------------------------------------

def member_out(m: Membership, manager: bool) -> dict:
    d = {"id": str(m.id), "status": m.status, "role": {"id": str(m.role.id), "name": m.role.name},
         "joined_at": iso(m.joined_at),
         "user": {"username": m.user.username, "full_name": m.user.full_name, "avatar_url": m.user.avatar_url,
                  "department": m.user.department, "class_year": m.user.class_year}}
    if manager:
        d["user"]["email"] = m.user.email
        d["notes"] = m.notes
        d["application"] = m.application
    return d


@router.get("/{slug}/members")
def list_members(status: str | None = None, role_id: UUID | None = None, q: str | None = None, limit: int = 50, offset: int = 0,
                 ctx: ClubCtx = Depends(club_perm("members.view")), db: Session = Depends(get_db)):
    query = select(Membership).join(User, User.id == Membership.user_id).where(Membership.club_id == ctx.club.id)
    if status:
        query = query.where(Membership.status == status)
    if role_id:
        query = query.where(Membership.role_id == role_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(User.full_name.ilike(like), User.username.ilike(like)))
    rows = db.scalars(query.order_by(User.full_name).limit(min(limit, 100)).offset(offset)).unique().all()
    manager = has_perm(ctx.membership, "members.manage")
    return [member_out(m, manager) for m in rows]


class MemberUpdate(BaseModel):
    status: Literal["active", "suspended", "rejected", "former"] | None = None
    role_id: UUID | None = None
    notes: str | None = Field(None, max_length=2000)


def _actor_rank(m: Membership) -> int:
    return m.role.rank


def _is_owner(m: Membership) -> bool:
    return "*" in (m.role.permissions or [])


def _last_owner_guard(db: Session, club_id, target: Membership):
    owners = db.scalars(select(Membership).where(Membership.club_id == club_id, Membership.status == "active")).unique().all()
    if _is_owner(target) and len([o for o in owners if _is_owner(o)]) <= 1:
        raise HTTPException(400, "A club must keep at least one active Owner")


@router.patch("/{slug}/members/{member_id}")
def update_member(member_id: UUID, body: MemberUpdate, ctx: ClubCtx = Depends(club_perm("members.manage")), db: Session = Depends(get_db)):
    target = db.scalar(select(Membership).where(Membership.id == member_id, Membership.club_id == ctx.club.id))
    if not target:
        raise HTTPException(404, "Member not found")
    if target.id == ctx.membership.id and (body.status or body.role_id):
        raise HTTPException(400, "You cannot change your own role or status")
    if not _is_owner(ctx.membership) and _actor_rank(ctx.membership) <= target.role.rank:
        raise HTTPException(403, "You can only manage members ranked below you")
    lock_club(db, ctx.club.id)
    changes = {}
    old_rank = target.role.rank
    if body.role_id:
        new_role = db.scalar(select(Role).where(Role.id == body.role_id, Role.club_id == ctx.club.id))
        if not new_role:
            raise HTTPException(404, "Role not found")
        if not _is_owner(ctx.membership) and new_role.rank >= _actor_rank(ctx.membership):
            raise HTTPException(403, "You cannot assign a role at or above your own")
        if new_role.id != target.role_id:
            if _is_owner(target) and not _is_owner(Membership(role=new_role, status="active")):
                _last_owner_guard(db, ctx.club.id, target)
            changes["role"] = f"{target.role.name} -> {new_role.name}"
            target.role_id, target.role = new_role.id, new_role
    will_be_active = (body.status or target.status) == "active"
    if will_be_active and target.role.rank >= ADMIN_RANK and not (target.status == "active" and old_rank >= ADMIN_RANK):
        with db.no_autoflush:  # count the DB state, before this member's pending change
            require_room(db, ctx.club, "admins", count_admins(db, ctx.club.id), "admin seats")
    if body.status and body.status != target.status:
        if body.status == "active":
            _check_member_limit(db, ctx.club)
            target.joined_at = target.joined_at or utcnow()
        elif target.status == "active" and _is_owner(target):
            _last_owner_guard(db, ctx.club.id, target)
        changes["status"] = f"{target.status} -> {body.status}"
        was_pending = target.status == "pending"
        target.status = body.status
        if was_pending and body.status in ("active", "rejected"):
            word = "approved" if body.status == "active" else "declined"
            notify(db, target.user_id, f"Your request to join {ctx.club.name} was {word}", link=f"/c/{ctx.club.slug}")
            queue_email(db, to=target.user.email, subject=f"{ctx.club.name}: membership {word}",
                        body=f"Hi {target.user.full_name.split()[0]},\n\nYour request to join {ctx.club.name} was {word}.\n{settings.base_url}/c/{ctx.club.slug}\n",
                        club_id=ctx.club.id)
    if body.notes is not None:
        target.notes = body.notes
        changes["notes"] = "updated"
    audit(db, ctx.club.id, ctx.user.id, "member.updated", target.user.username, changes)
    db.commit()
    return member_out(target, True)


@router.delete("/{slug}/members/{member_id}")
def remove_member(member_id: UUID, ctx: ClubCtx = Depends(club_perm("members.manage")), db: Session = Depends(get_db)):
    target = db.scalar(select(Membership).where(Membership.id == member_id, Membership.club_id == ctx.club.id))
    if not target:
        raise HTTPException(404, "Member not found")
    if target.id == ctx.membership.id:
        raise HTTPException(400, "Leave the club instead of removing yourself")
    if not _is_owner(ctx.membership) and _actor_rank(ctx.membership) <= target.role.rank:
        raise HTTPException(403, "You can only manage members ranked below you")
    if target.status == "active":
        _last_owner_guard(db, ctx.club.id, target)
    target.status = "former"
    audit(db, ctx.club.id, ctx.user.id, "member.removed", target.user.username)
    db.commit()
    return {"ok": True}


@router.post("/{slug}/leave")
def leave(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    m = get_membership(db, club.id, user.id)
    if not m or m.status not in ("active", "pending", "invited"):
        raise HTTPException(404, "Not a member")
    if m.status == "active":
        _last_owner_guard(db, club.id, m)
    m.status = "former"
    audit(db, club.id, user.id, "member.left", user.username)
    db.commit()
    return {"ok": True}


class InviteIn(BaseModel):
    username: str


@router.post("/{slug}/invites", status_code=201)
def invite(body: InviteIn, ctx: ClubCtx = Depends(club_perm("members.manage")), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.username == body.username))
    if not target:
        raise HTTPException(404, "User not found")
    m = get_membership(db, ctx.club.id, target.id)
    if m and m.status in ("active", "pending", "invited", "suspended", "rejected"):
        raise HTTPException(409, f"User is already {m.status}")
    if m:
        m.status = "invited"
    else:
        db.add(Membership(club_id=ctx.club.id, user_id=target.id, role_id=_role(db, ctx.club.id, "Member").id, status="invited"))
    notify(db, target.id, f"You were invited to {ctx.club.name}", link=f"/c/{ctx.club.slug}")
    audit(db, ctx.club.id, ctx.user.id, "member.invited", target.username)
    db.commit()
    return {"ok": True}


# ---- roles ---------------------------------------------------------------------------------

class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    permissions: list[str] = []
    rank: int = Field(30, ge=1, le=89)


def _check_role_grant(ctx: ClubCtx, perms: list[str], rank: int):
    bad = [p for p in perms if p not in PERMS]
    if bad:
        raise HTTPException(422, f"Unknown permissions: {bad}")
    if not _is_owner(ctx.membership):
        mine = set(ctx.membership.role.permissions or [])
        if not set(perms) <= mine:
            raise HTTPException(403, "You cannot grant permissions you don't have")  # privilege-escalation guard
        if rank >= _actor_rank(ctx.membership):
            raise HTTPException(403, "You cannot create a role at or above your own rank")


def role_out(r: Role) -> dict:
    return {"id": str(r.id), "name": r.name, "permissions": r.permissions, "rank": r.rank, "is_system": r.is_system}


@router.get("/{slug}/roles")
def list_roles(ctx: ClubCtx = Depends(club_perm(None)), db: Session = Depends(get_db)):
    return [role_out(r) for r in db.scalars(select(Role).where(Role.club_id == ctx.club.id).order_by(Role.rank.desc()))]


@router.post("/{slug}/roles", status_code=201)
def create_role(body: RoleIn, ctx: ClubCtx = Depends(club_perm("roles.manage")), db: Session = Depends(get_db)):
    _check_role_grant(ctx, body.permissions, body.rank)
    if db.scalar(select(Role.id).where(Role.club_id == ctx.club.id, Role.name == body.name)):
        raise HTTPException(409, "Role name already exists")
    r = Role(club_id=ctx.club.id, name=body.name, permissions=sorted(set(body.permissions)), rank=body.rank)
    db.add(r)
    audit(db, ctx.club.id, ctx.user.id, "role.created", body.name, {"permissions": r.permissions})
    db.commit()
    return role_out(r)


@router.patch("/{slug}/roles/{role_id}")
def update_role(role_id: UUID, body: RoleIn, ctx: ClubCtx = Depends(club_perm("roles.manage")), db: Session = Depends(get_db)):
    r = db.scalar(select(Role).where(Role.id == role_id, Role.club_id == ctx.club.id))
    if not r:
        raise HTTPException(404, "Role not found")
    if r.is_system:
        raise HTTPException(400, "System roles cannot be edited; create a custom role instead")
    if not _is_owner(ctx.membership) and r.rank >= _actor_rank(ctx.membership):
        raise HTTPException(403, "You cannot edit a role at or above your own rank")
    _check_role_grant(ctx, body.permissions, body.rank)
    r.name, r.permissions, r.rank = body.name, sorted(set(body.permissions)), body.rank
    audit(db, ctx.club.id, ctx.user.id, "role.updated", r.name, {"permissions": r.permissions})
    db.commit()
    return role_out(r)


@router.delete("/{slug}/roles/{role_id}")
def delete_role(role_id: UUID, ctx: ClubCtx = Depends(club_perm("roles.manage")), db: Session = Depends(get_db)):
    r = db.scalar(select(Role).where(Role.id == role_id, Role.club_id == ctx.club.id))
    if not r:
        raise HTTPException(404, "Role not found")
    if r.is_system:
        raise HTTPException(400, "System roles cannot be deleted")
    if not _is_owner(ctx.membership) and r.rank >= _actor_rank(ctx.membership):
        raise HTTPException(403, "You cannot delete a role at or above your own rank")
    if db.scalar(select(func.count()).select_from(Membership).where(Membership.role_id == r.id)):
        raise HTTPException(409, "Reassign members before deleting this role")
    audit(db, ctx.club.id, ctx.user.id, "role.deleted", r.name)
    db.delete(r)
    db.commit()
    return {"ok": True}


# ---- audit + dashboard ---------------------------------------------------------------------

@router.get("/{slug}/audit")
def audit_log(limit: int = 100, ctx: ClubCtx = Depends(club_perm("audit.view")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.club_id == ctx.club.id).order_by(AuditLog.created_at.desc()).limit(min(limit, 200))).all()
    actors = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_({r.actor_id for r in rows if r.actor_id})))}
    return [{"at": iso(r.created_at), "actor": actors.get(r.actor_id), "action": r.action, "target": r.target, "meta": r.meta} for r in rows]


@router.get("/{slug}/dashboard")
def dashboard(ctx: ClubCtx = Depends(club_perm(None)), db: Session = Depends(get_db)):
    """What happened / what needs attention / what can I do. Sections are filtered by the caller's permissions."""
    club, m, now = ctx.club, ctx.membership, utcnow()
    out: dict = {"club": {"slug": club.slug, "name": club.name, "plan": club.plan}, "attention": {}, "recent": {}, "actions": []}
    if has_perm(m, "members.view"):
        out["stats"] = {"active_members": _active_count(db, club.id)}
    if has_perm(m, "members.manage"):
        out["attention"]["pending_members"] = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.club_id == club.id, Membership.status == "pending"))
        out["actions"].append("review_applications")
    if has_perm(m, "events.manage"):
        ups = db.scalars(select(Event).where(Event.club_id == club.id, Event.status == "published", Event.starts_at >= now)
                         .order_by(Event.starts_at).limit(5)).unique().all()
        out["upcoming_events"] = [{"slug": e.slug, "title": e.title, "starts_at": iso(e.starts_at), "capacity": e.capacity} for e in ups]
        recent = db.scalars(select(Registration).join(Event, Event.id == Registration.event_id).where(Event.club_id == club.id)
                            .order_by(Registration.created_at.desc()).limit(8)).unique().all()
        out["recent"]["registrations"] = [{"name": r.user.full_name, "event": r.event.title, "status": r.status, "at": iso(r.created_at)} for r in recent]
        out["actions"] += ["create_event"]
    if has_perm(m, "posts.manage"):
        out["actions"].append("create_post")
    if has_perm(m, "comms.send"):
        out["actions"].append("send_announcement")
    if has_perm(m, "audit.view"):
        rows = db.scalars(select(AuditLog).where(AuditLog.club_id == club.id).order_by(AuditLog.created_at.desc()).limit(8)).all()
        out["recent"]["activity"] = [{"action": r.action, "target": r.target, "at": iso(r.created_at)} for r in rows]
    return out
