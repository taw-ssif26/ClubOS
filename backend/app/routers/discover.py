from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import can_view_club, current_user_optional, get_club_or_404, get_membership
from ..models import Club, Event, Institution, Post, Review, User, utcnow
from ..services.core import ONGOING_GRACE, event_phase, iso
from ..services.geo import check_coords
from ..services.places import haversine_km
from ..services.plans import branding_visible
from ..services.reviews import rating_for, rating_map
from .clubs import club_out
from .events import event_out

router = APIRouter(tags=["discover"])
Mode = Literal["onsite", "online", "hybrid"]


def _like(q: str) -> str:
    return "%" + q.strip().replace("%", r"\%").replace("_", r"\_") + "%"


def _origin(user: User | None, near: bool, lat: float | None, lng: float | None):
    """Where 'near me' is measured from: explicit coordinates, else the signed-in user's saved location."""
    if lat is not None or lng is not None:
        check_coords(lat, lng)
        return (lat, lng)
    if near and user and user.latitude is not None:
        return (user.latitude, user.longitude)
    return None


def _distance(obj, origin):
    if not origin or obj.latitude is None or obj.location_mode == "online":
        return None
    return round(haversine_km(origin[0], origin[1], obj.latitude, obj.longitude), 1)


def _rank_by_distance(items: list, origin, max_km: float | None) -> list:
    """items: [(obj, distance|None)]. Nearest first; things with no physical position (online, or no place set) follow."""
    if max_km is not None:
        items = [(o, d) for o, d in items if d is None or d <= max_km]
    return sorted(items, key=lambda t: (t[1] is None, t[1] if t[1] is not None else 0))


def _public_clubs(q: str | None, category: str | None, institution: str | None, mode: str | None = None, place: str | None = None):
    s = select(Club).where(Club.visibility == "public", Club.status == "approved")
    if q:
        s = s.where(or_(Club.name.ilike(_like(q), escape="\\"), Club.description.ilike(_like(q), escape="\\")))
    if category:
        s = s.where(Club.category == category)
    if mode:
        s = s.where(Club.location_mode == mode)
    if place:
        s = s.where(Club.place == place)
    if institution:
        s = s.join(Institution, Institution.id == Club.institution_id).where(Institution.slug == institution)
    return s


def _public_events(q: str | None, category: str | None, past: bool = False, mode: str | None = None, place: str | None = None):
    s = select(Event).join(Club, Club.id == Event.club_id).where(
        Event.status == "published", Event.visibility == "public", Club.visibility == "public", Club.status == "approved")
    if not past:   # upcoming AND ongoing
        now = utcnow()
        s = s.where(or_(Event.ends_at >= now, and_(Event.ends_at.is_(None), Event.starts_at >= now - ONGOING_GRACE)))
    if q:
        s = s.where(or_(Event.title.ilike(_like(q), escape="\\"), Event.description.ilike(_like(q), escape="\\")))
    if category:
        s = s.where(Club.category == category)
    if mode:
        s = s.where(Event.location_mode == mode)
    if place:
        s = s.where(Event.place == place)
    return s


@router.get("/discover/clubs")
def discover_clubs(q: str | None = None, category: str | None = None, institution: str | None = None, verified: bool | None = None,
                   mode: Mode | None = None, place: str | None = None, near: bool = False, lat: float | None = None, lng: float | None = None,
                   max_km: float | None = None, sort: str = "rating", limit: int = 20, offset: int = 0,
                   user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    s = _public_clubs(q, category, institution, mode, place)
    if verified is not None:
        s = s.where(Club.verified.is_(verified))
    origin = _origin(user, near, lat, lng)
    limit = min(limit, 50)
    if sort == "nearest" and origin:
        rows = db.scalars(s.limit(2000)).unique().all()
        ranked = _rank_by_distance([(c, _distance(c, origin)) for c in rows], origin, max_km)[offset:offset + limit]
        page = [(c, d) for c, d in ranked]
    else:
        if sort == "rating":
            agg = (select(Review.club_id.label("cid"), func.avg(Review.rating).label("avg")).where(Review.target_type == "club", Review.status == "published")
                   .group_by(Review.club_id).subquery())
            s = s.outerjoin(agg, agg.c.cid == Club.id).order_by(agg.c.avg.desc().nulls_last(), Club.verified.desc(), Club.name)
        else:
            s = s.order_by(Club.verified.desc(), Club.name)
        page = [(c, _distance(c, origin)) for c in db.scalars(s.limit(limit).offset(offset)).unique().all()]
    ratings = rating_map(db, [f"club:{c.id}" for c, _ in page])
    return [club_out(c, rating=ratings.get(f"club:{c.id}", {"average": None, "count": 0})) | {"application_fields": None, "distance_km": d} for c, d in page]


@router.get("/discover/events")
def discover_events(q: str | None = None, category: str | None = None, mode: Mode | None = None, place: str | None = None,
                    near: bool = False, lat: float | None = None, lng: float | None = None, max_km: float | None = None,
                    sort: str = "soonest", limit: int = 20, offset: int = 0,
                    user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    s = _public_events(q, category, mode=mode, place=place)
    origin = _origin(user, near, lat, lng)
    limit = min(limit, 50)
    if sort == "nearest" and origin:
        rows = db.scalars(s.order_by(Event.starts_at).limit(2000)).unique().all()
        page = _rank_by_distance([(e, _distance(e, origin)) for e in rows], origin, max_km)[offset:offset + limit]
    else:
        page = [(e, _distance(e, origin)) for e in db.scalars(s.order_by(Event.starts_at).limit(limit).offset(offset)).unique().all()]
    return [event_out(db, e, detail=False) | {"distance_km": d} for e, d in page]


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
    rows = db.scalars(select(Event).where(Event.club_id == club.id, Event.status == "published", Event.visibility == "public")
                      .order_by(Event.starts_at.desc()).limit(120)).unique().all()
    now = utcnow()
    ongoing = [e for e in rows if event_phase(e, now) == "ongoing"]
    upcoming = sorted([e for e in rows if event_phase(e, now) == "upcoming"], key=lambda e: e.starts_at)
    past = [e for e in rows if event_phase(e, now) == "past"][:12]           # rows are newest first
    c = club_out(club, m, rating_for(db, f"club:{club.id}"), branding_visible(db, club))
    c["application_fields"] = club.application_fields
    return {"club": c,
            "posts": [{"id": str(p.id), "title": p.title, "body": p.body, "kind": p.kind, "pinned": p.pinned, "created_at": iso(p.created_at),
                       "attachments": p.attachments or []} for p in posts],
            "events": [event_out(db, e, detail=False) for e in ongoing + upcoming][:12],
            "past_events": [event_out(db, e, detail=False) for e in past]}


@router.get("/institutions/{slug}")
def institution(slug: str, db: Session = Depends(get_db)):
    inst = db.scalar(select(Institution).where(Institution.slug == slug))
    if not inst:
        raise HTTPException(404, "Institution not found")
    clubs = db.scalars(select(Club).where(Club.institution_id == inst.id, Club.visibility == "public", Club.status == "approved").order_by(Club.name)).unique().all()
    return {"slug": inst.slug, "name": inst.name, "description": inst.description, "verified": inst.verified,
            "clubs": [{"slug": c.slug, "name": c.name, "category": c.category, "verified": c.verified} for c in clubs]}
