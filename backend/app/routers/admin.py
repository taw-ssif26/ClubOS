import re
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_club_or_404, platform_admin, verified_user
from ..models import (AuditLog, Club, EmailOutbox, Event, Institution, Membership, Offer, Plan, Registration, Review, SiteContent,
                      Session as UserSession, UpgradeRequest, User, aware, utcnow)
from ..seed import DEFAULT_CONTENT, FLAGS
from ..services.core import audit, iso, notify, to_utc
from ..services.mail import queue_email
from .site import offer_out, plan_out

router = APIRouter(tags=["platform"])


# ---- institutions --------------------------------------------------------------------------

class InstitutionIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,59}$")
    description: str = Field("", max_length=3000)
    email_domain: str | None = Field(None, pattern=r"^[a-z0-9.-]+\.[a-z]{2,}$")


@router.post("/institutions", status_code=201)
def create_institution(body: InstitutionIn, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    if db.scalar(select(Institution.id).where(Institution.slug == body.slug)):
        raise HTTPException(409, "Slug already taken")
    inst = Institution(**body.model_dump(), created_by=user.id)
    db.add(inst)
    db.commit()
    return {"slug": inst.slug, "name": inst.name, "verified": False}


@router.post("/admin/institutions/{slug}/verify")
def verify_institution(slug: str, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    inst = db.scalar(select(Institution).where(Institution.slug == slug))
    if not inst:
        raise HTTPException(404, "Institution not found")
    inst.verified = True
    audit(db, None, admin.id, "institution.verified", slug)
    db.commit()
    return {"ok": True}


# ---- clubs ---------------------------------------------------------------------------------

@router.get("/admin/clubs")
def admin_clubs(q: str | None = None, limit: int = 50, offset: int = 0, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    s = select(Club)
    if q:
        s = s.where(or_(Club.name.ilike(f"%{q}%"), Club.slug.ilike(f"%{q}%")))
    rows = db.scalars(s.order_by(Club.created_at.desc()).limit(min(limit, 100)).offset(offset)).unique().all()
    counts = dict(db.execute(select(Membership.club_id, func.count()).where(Membership.status == "active").group_by(Membership.club_id)).all())
    return [{"slug": c.slug, "name": c.name, "plan": c.plan, "plan_expires_at": iso(c.plan_expires_at), "verified": c.verified,
             "visibility": c.visibility, "members": counts.get(c.id, 0), "created_at": iso(c.created_at)} for c in rows]


@router.post("/admin/clubs/{slug}/verify")
def verify_club(slug: str, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    club.verified = True
    audit(db, club.id, admin.id, "club.verified", club.slug)
    db.commit()
    return {"ok": True}


class PlanSetIn(BaseModel):
    plan: str
    months: int = Field(1, ge=1, le=36)


def _apply_plan(db: Session, club: Club, plan_key: str, months: int):
    if not db.scalar(select(Plan.id).where(Plan.key == plan_key)):
        raise HTTPException(404, "Unknown plan")
    if plan_key == "free":
        club.plan, club.plan_expires_at = "free", None
        return
    exp = aware(club.plan_expires_at)
    base = exp if (club.plan == plan_key and exp and exp > utcnow()) else utcnow()  # renewals extend, not reset
    club.plan, club.plan_expires_at = plan_key, base + timedelta(days=30 * months)


@router.post("/admin/clubs/{slug}/plan")
def set_plan(slug: str, body: PlanSetIn, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    _apply_plan(db, club, body.plan, body.months)
    audit(db, club.id, admin.id, "club.plan_changed", body.plan, {"months": body.months})
    db.commit()
    return {"ok": True, "plan": club.plan, "expires_at": iso(club.plan_expires_at)}


# ---- upgrade requests ----------------------------------------------------------------------

@router.get("/admin/upgrade-requests")
def upgrade_requests(status: str = "pending", admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(UpgradeRequest).where(UpgradeRequest.status == status).order_by(UpgradeRequest.created_at)).unique()
    return [{"id": str(r.id), "club": {"slug": r.club.slug, "name": r.club.name, "plan": r.club.plan}, "requested_by": r.user.full_name,
             "plan_key": r.plan_key, "months": r.months, "contact": r.contact, "message": r.message, "created_at": iso(r.created_at)} for r in rows]


class DecisionIn(BaseModel):
    note: str = Field("", max_length=500)


@router.post("/admin/upgrade-requests/{rid}/approve")
def approve_upgrade(rid: UUID, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    r = db.get(UpgradeRequest, rid)
    if not r or r.status != "pending":
        raise HTTPException(404, "Pending request not found")
    _apply_plan(db, r.club, r.plan_key, r.months)
    r.status = "approved"
    notify(db, r.user_id, f"{r.club.name} is now on {r.plan_key.title()}", link=f"/manage/{r.club.slug}")
    queue_email(db, to=r.user.email, subject=f"{r.club.name} upgraded to {r.plan_key.title()}", club_id=r.club_id,
                body=f"Payment confirmed. {r.club.name} is on the {r.plan_key.title()} plan until {iso(r.club.plan_expires_at)[:10]}.\n{settings.base_url}/manage/{r.club.slug}\n")
    audit(db, r.club_id, admin.id, "billing.upgrade_approved", r.plan_key, {"months": r.months})
    db.commit()
    return {"ok": True}


@router.post("/admin/upgrade-requests/{rid}/reject")
def reject_upgrade(rid: UUID, body: DecisionIn, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    r = db.get(UpgradeRequest, rid)
    if not r or r.status != "pending":
        raise HTTPException(404, "Pending request not found")
    r.status = "rejected"
    notify(db, r.user_id, "Upgrade request not approved", body.note or "Contact us if you think this is a mistake.")
    audit(db, r.club_id, admin.id, "billing.upgrade_rejected", r.plan_key)
    db.commit()
    return {"ok": True}


# ---- content (CMS) -------------------------------------------------------------------------

@router.get("/admin/content")
def admin_content(admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    rows = {c.key: c for c in db.scalars(select(SiteContent))}
    return [{"key": k, "value": rows[k].value if k in rows else DEFAULT_CONTENT[k], "updated_at": iso(rows[k].updated_at) if k in rows else None}
            for k in DEFAULT_CONTENT]


class ContentIn(BaseModel):
    value: dict


@router.put("/admin/content/{key}")
def put_content(key: str, body: ContentIn, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    if key not in DEFAULT_CONTENT:
        raise HTTPException(404, "Unknown content key")
    if len(str(body.value)) > 60000:
        raise HTTPException(413, "Content too large")
    row = db.scalar(select(SiteContent).where(SiteContent.key == key))
    if not row:
        row = SiteContent(key=key, value=body.value)
        db.add(row)
    row.value, row.updated_by = body.value, admin.id
    audit(db, None, admin.id, "content.updated", key)
    db.commit()
    return {"ok": True}


@router.post("/admin/content/{key}/reset")
def reset_content(key: str, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    if key not in DEFAULT_CONTENT:
        raise HTTPException(404, "Unknown content key")
    row = db.scalar(select(SiteContent).where(SiteContent.key == key))
    if row:
        row.value, row.updated_by = DEFAULT_CONTENT[key], admin.id
    audit(db, None, admin.id, "content.reset", key)
    db.commit()
    return {"ok": True}


# ---- plans ---------------------------------------------------------------------------------

LIMIT_KEYS = ["members", "admins", "active_events", "storage_mb", "emails_per_day"]


class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    tagline: str = Field("", max_length=200)
    price_monthly: int | None = Field(None, ge=0, le=10_000_000)
    price_label: str = Field("", max_length=80)
    cta_label: str = Field("Choose plan", max_length=60)
    limits: dict
    features: list[dict] = []
    highlighted: bool = False
    visible: bool = True
    sort: int = 0


def _clean_limits(raw: dict) -> dict:
    out = {}
    for k in LIMIT_KEYS:
        v = raw.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            raise HTTPException(422, f"limits.{k} must be a non-negative integer or null (unlimited)")
        out[k] = v
    for k in FLAGS:
        out[k] = bool(raw.get(k, False))
    return out


@router.get("/admin/plans")
def admin_plans(admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    return [plan_out(p) for p in db.scalars(select(Plan).order_by(Plan.sort))]


@router.put("/admin/plans/{key}")
def put_plan(key: str, body: PlanIn, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    if not re.match(r"^[a-z][a-z0-9_]{1,29}$", key):
        raise HTTPException(422, "Invalid plan key")
    feats = []
    for ft in body.features[:60]:
        label = str(ft.get("label", "")).strip()[:160]
        if label:
            feats.append({"label": label, "status": "soon" if ft.get("status") == "soon" else "live"})
    p = db.scalar(select(Plan).where(Plan.key == key)) or Plan(key=key)
    p.name, p.tagline, p.price_monthly, p.price_label, p.cta_label = body.name, body.tagline, body.price_monthly, body.price_label, body.cta_label
    p.limits, p.features, p.highlighted, p.visible, p.sort = _clean_limits(body.limits), feats, body.highlighted, body.visible, body.sort
    db.add(p)
    audit(db, None, admin.id, "plan.updated", key)
    db.commit()
    return plan_out(p)


# ---- offers --------------------------------------------------------------------------------

class OfferIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: str = Field("", max_length=400)
    badge: str = Field("", max_length=40)
    cta_label: str = Field("", max_length=60)
    cta_url: str = Field("", max_length=300, pattern=r"^(|/[^\s]*|https?://[^\s]+)$")
    plan_key: str | None = None
    discount_percent: int = Field(0, ge=0, le=100)
    placement: Literal["banner", "pricing", "both"] = "banner"
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    active: bool = True


@router.get("/admin/offers")
def admin_offers(admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    return [offer_out(o) for o in db.scalars(select(Offer).order_by(Offer.created_at.desc()))]


@router.post("/admin/offers", status_code=201)
def create_offer(body: OfferIn, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["starts_at"], data["ends_at"] = to_utc(data["starts_at"]), to_utc(data["ends_at"])
    o = Offer(**data)
    db.add(o)
    audit(db, None, admin.id, "offer.created", body.title[:80])
    db.commit()
    return offer_out(o)


@router.put("/admin/offers/{oid}")
def update_offer(oid: UUID, body: OfferIn, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    o = db.get(Offer, oid)
    if not o:
        raise HTTPException(404, "Offer not found")
    for k, v in body.model_dump().items():
        setattr(o, k, to_utc(v) if k in ("starts_at", "ends_at") else v)
    audit(db, None, admin.id, "offer.updated", o.title[:80])
    db.commit()
    return offer_out(o)


@router.delete("/admin/offers/{oid}")
def delete_offer(oid: UUID, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    o = db.get(Offer, oid)
    if not o:
        raise HTTPException(404, "Offer not found")
    db.delete(o)
    audit(db, None, admin.id, "offer.deleted", o.title[:80])
    db.commit()
    return {"ok": True}


# ---- review moderation ---------------------------------------------------------------------

@router.get("/admin/reviews")
def admin_reviews(status: str = "published", reported: bool = False, limit: int = 50, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Review).where(Review.status == status).order_by(Review.created_at.desc()).limit(200)).unique().all()
    if reported:
        rows = sorted((r for r in rows if r.reporters), key=lambda r: -len(r.reporters))
    return [{"id": str(r.id), "rating": r.rating, "title": r.title, "body": r.body, "status": r.status, "reports": len(r.reporters or []),
             "user": r.user.full_name, "club": r.club.name, "type": r.target_type, "created_at": iso(r.created_at)} for r in rows[:limit]]


@router.post("/admin/reviews/{rid}/{action}")
def moderate_review(rid: UUID, action: Literal["hide", "unhide", "delete"], admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    r = db.get(Review, rid)
    if not r:
        raise HTTPException(404, "Review not found")
    if action == "delete":
        db.delete(r)
    else:
        r.status = "hidden" if action == "hide" else "published"
        if action == "unhide":
            r.reporters = []
    audit(db, r.club_id, admin.id, f"review.{action}", str(rid))
    db.commit()
    return {"ok": True}


# ---- users + stats + audit -----------------------------------------------------------------

@router.get("/admin/users")
def admin_users(q: str | None = None, limit: int = 50, offset: int = 0, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    s = select(User)
    if q:
        s = s.where(or_(User.email.ilike(f"%{q}%"), User.username.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    rows = db.scalars(s.order_by(User.created_at.desc()).limit(min(limit, 100)).offset(offset)).all()
    return [{"id": str(u.id), "email": u.email, "username": u.username, "full_name": u.full_name, "verified": u.email_verified,
             "active": u.is_active, "admin": u.is_platform_admin, "created_at": iso(u.created_at)} for u in rows]


@router.post("/admin/users/{uid}/{action}")
def user_action(uid: UUID, action: Literal["suspend", "unsuspend"], admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if u.is_platform_admin:
        raise HTTPException(400, "Platform admins can't be suspended here")
    u.is_active = action == "unsuspend"
    if action == "suspend":
        for s in db.scalars(select(UserSession).where(UserSession.user_id == u.id, UserSession.revoked.is_(False))):
            s.revoked = True
    audit(db, None, admin.id, f"user.{action}", u.username)
    db.commit()
    return {"ok": True}


@router.get("/admin/stats")
def stats(admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    c = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w))  # noqa: E731
    by_plan = dict(db.execute(select(Club.plan, func.count()).group_by(Club.plan)).all())
    return {"users": c(User), "clubs": c(Club), "events": c(Event), "registrations": c(Registration), "reviews": c(Review),
            "clubs_by_plan": by_plan, "pending_upgrades": c(UpgradeRequest, UpgradeRequest.status == "pending"),
            "reported_reviews": len([1 for r in db.scalars(select(Review).where(Review.status == "published")) if r.reporters]),
            "emails_pending": c(EmailOutbox, EmailOutbox.status == "pending"), "emails_failed": c(EmailOutbox, EmailOutbox.status == "failed")}


@router.get("/admin/audit")
def platform_audit(limit: int = 100, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.club_id.is_(None)).order_by(AuditLog.created_at.desc()).limit(min(limit, 200))).all()
    names = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_({r.actor_id for r in rows if r.actor_id})))}
    return [{"at": iso(r.created_at), "actor": names.get(r.actor_id), "action": r.action, "target": r.target} for r in rows]
