from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import can_view_club, current_user_optional, get_club_or_404, get_membership
from ..models import Club, Event, Institution, Post, Review, User, utcnow
from ..services.plans import branding_visible
from ..services.reviews import rating_map, rating_for
from sqlalchemy import func
from ..services.core import iso
from .clubs import club_out
from .events import event_out

router = APIRouter(tags=["discover"])


def _like(q: str) -> str:
    return "%" + q.strip().replace("%", r"\%").replace("_", r"\_") + "%"


def _public_clubs(q: str | None, category: str | None, institution: str | None):
    s = select(Club).where(Club.visibility == "public")
    if q:
        s = s.where(or_(Club.name.ilike(_like(q), escape="\\"), Club.description.ilike(_like(q), escape="\\")))
    if category:
        s = s.where(Club.category == category)
    if institution:
        s = s.join(Institution, Institution.id == Club.institution_id).where(Institution.slug == institution)
    return s


def _public_events(q: str | None, category: str | None, past: bool = False):
    s = select(Event).join(Club, Club.id == Event.club_id).where(
        Event.status == "published", Event.visibility == "public", Club.visibility == "public")
    if not past:
        s = s.where(Event.starts_at >= utcnow())
    if q:
        s = s.where(or_(Event.title.ilike(_like(q), escape="\\"), Event.description.ilike(_like(q), escape="\\")))
    if category:
        s = s.where(Club.category == category)
    return s


@router.get("/discover/clubs")
def discover_clubs(q: str | None = None, category: str | None = None, institution: str | None = None,
                   verified: bool | None = None, sort: str = "rating", limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    s = _public_clubs(q, category, institution)
    if verified is not None:
        s = s.where(Club.verified.is_(verified))
    if sort == "rating":
        agg = (select(Review.club_id.label("cid"), func.avg(Review.rating).label("avg")).where(Review.target_type == "club", Review.status == "published")
               .group_by(Review.club_id).subquery())
        s = s.outerjoin(agg, agg.c.cid == Club.id).order_by(agg.c.avg.desc().nulls_last(), Club.verified.desc(), Club.name)
    else:
        s = s.order_by(Club.verified.desc(), Club.name)
    rows = db.scalars(s.limit(min(limit, 50)).offset(offset)).unique().all()
    ratings = rating_map(db, [f"club:{c.id}" for c in rows])
    return [club_out(c, rating=ratings.get(f"club:{c.id}", {"average": None, "count": 0})) | {"application_fields": None} for c in rows]


@router.get("/discover/events")
def discover_events(q: str | None = None, category: str | None = None, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    rows = db.scalars(_public_events(q, category).order_by(Event.starts_at).limit(min(limit, 50)).offset(offset)).unique().all()
    return [event_out(db, e, detail=False) for e in rows]


@router.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    """Global search over PUBLIC objects only. Private data is never indexed here."""
    if len(q.strip()) < 2:
        return {"clubs": [], "events": [], "people": []}
    clubs = db.scalars(_public_clubs(q, None, None).limit(8)).unique().all()
    events = db.scalars(_public_events(q, None).order_by(Event.starts_at).limit(8)).unique().all()
    people = db.scalars(select(User).where(User.profile_public.is_(True), User.is_active.is_(True),
                                           or_(User.full_name.ilike(_like(q), escape="\\"), User.username.ilike(_like(q), escape="\\"))).limit(8)).all()
    return {"clubs": [{"slug": c.slug, "name": c.name} for c in clubs],
            "events": [{"slug": e.slug, "title": e.title, "starts_at": iso(e.starts_at)} for e in events],
            "people": [{"username": u.username, "full_name": u.full_name} for u in people]}


@router.get("/public/clubs/{slug}")
def public_club_page(slug: str, user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    """Everything the public club website needs in one request (SSR-friendly)."""
    club = get_club_or_404(db, slug)
    m = get_membership(db, club.id, user.id if user else None)
    if not can_view_club(db, club, user, m):
        raise HTTPException(404, "Club not found")
    posts = db.scalars(select(Post).where(Post.club_id == club.id, Post.status == "published",
                                          or_(Post.publish_at.is_(None), Post.publish_at <= utcnow()))
                       .order_by(Post.pinned.desc(), Post.created_at.desc()).limit(10)).all()
    events = db.scalars(select(Event).where(Event.club_id == club.id, Event.status == "published", Event.visibility == "public",
                                            Event.starts_at >= utcnow()).order_by(Event.starts_at).limit(10)).unique().all()
    c = club_out(club, m, rating_for(db, f"club:{club.id}"), branding_visible(db, club))
    c["application_fields"] = club.application_fields
    return {"club": c,
            "posts": [{"id": str(p.id), "title": p.title, "body": p.body, "kind": p.kind, "pinned": p.pinned, "created_at": iso(p.created_at)} for p in posts],
            "events": [event_out(db, e, detail=False) for e in events]}


@router.get("/institutions/{slug}")
def institution(slug: str, db: Session = Depends(get_db)):
    inst = db.scalar(select(Institution).where(Institution.slug == slug))
    if not inst:
        raise HTTPException(404, "Institution not found")
    clubs = db.scalars(select(Club).where(Club.institution_id == inst.id, Club.visibility == "public").order_by(Club.name)).unique().all()
    return {"slug": inst.slug, "name": inst.name, "description": inst.description, "verified": inst.verified,
            "clubs": [{"slug": c.slug, "name": c.name, "category": c.category, "verified": c.verified} for c in clubs]}
