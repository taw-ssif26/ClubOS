"""Ratings and reviews for clubs and events. Only people who actually took part can review."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ClubCtx, can_view_club, can_view_event, club_perm, current_user, current_user_optional, get_club_or_404, get_membership
from ..models import Club, Event, Registration, Review, User, aware, utcnow
from ..permissions import ADMIN_RANK
from ..ratelimit import rate_limit
from ..services.core import audit, iso
from ..services.reviews import rating_for

router = APIRouter(tags=["reviews"])


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str = Field("", max_length=120)
    body: str = Field("", max_length=2000)


def public_name(u: User) -> str:
    """'Rahim U.': enough to be human, not enough to identify a student to strangers."""
    parts = u.full_name.split()
    return parts[0] if len(parts) < 2 else f"{parts[0]} {parts[-1][0]}."


def review_out(r: Review, viewer_id=None) -> dict:
    return {"id": str(r.id), "rating": r.rating, "title": r.title, "body": r.body, "created_at": iso(r.created_at),
            "mine": viewer_id is not None and r.user_id == viewer_id, "user": {"full_name": public_name(r.user)},
            "reply": r.reply, "reply_at": iso(r.reply_at), "club": {"slug": r.club.slug, "name": r.club.name}, "target_type": r.target_type}


def summary(db: Session, key: str) -> dict:
    s = rating_for(db, key)
    rows = dict(db.execute(select(Review.rating, func.count()).where(Review.target_key == key, Review.status == "published").group_by(Review.rating)).all())
    return {**s, "histogram": {str(i): rows.get(i, 0) for i in range(1, 6)}}


def _list(db: Session, key: str, user: User | None, limit: int, offset: int, eligibility) -> dict:
    items = db.scalars(select(Review).where(Review.target_key == key, Review.status == "published")
                       .order_by(Review.created_at.desc()).limit(min(limit, 50)).offset(offset)).unique().all()
    mine = db.scalar(select(Review).where(Review.target_key == key, Review.user_id == user.id)) if user else None
    ok, reason = eligibility() if user else (False, "Sign in to leave a review")
    return {"summary": summary(db, key), "items": [review_out(r, user.id if user else None) for r in items],
            "mine": review_out(mine, user.id) if mine else None, "can_review": ok, "reason": None if ok else reason}


def _club_eligible(db, club: Club, user: User):
    m = get_membership(db, club.id, user.id)
    if not m or m.status not in ("active", "former"):
        return False, "Only members and former members can review a club"
    if m.status == "active" and m.role.rank >= ADMIN_RANK:
        return False, "Club admins can't review their own club"
    return True, ""


def _event_eligible(db, event: Event, user: User):
    reg = db.scalar(select(Registration).where(Registration.event_id == event.id, Registration.user_id == user.id))
    if not reg or reg.status != "confirmed" or not reg.checked_in_at:
        return False, "Only people who checked in to this event can review it"
    m = get_membership(db, event.club_id, user.id)
    if m and m.status == "active" and m.role.rank >= ADMIN_RANK:
        return False, "Organizers can't review their own event"
    if aware(event.starts_at) > utcnow():
        return False, "Reviews open once the event has started"
    return True, ""


def _upsert(db: Session, key: str, ttype: str, club: Club, event: Event | None, user: User, body: ReviewIn) -> dict:
    r = db.scalar(select(Review).where(Review.target_key == key, Review.user_id == user.id))
    if r:
        r.rating, r.title, r.body = body.rating, body.title.strip(), body.body.strip()
        r.status = r.status if r.status == "hidden" else "published"
    else:
        r = Review(target_key=key, target_type=ttype, club_id=club.id, event_id=event.id if event else None, user_id=user.id,
                   rating=body.rating, title=body.title.strip(), body=body.body.strip())
        db.add(r)
    db.commit()
    return review_out(r)


def _delete(db: Session, key: str, user: User):
    r = db.scalar(select(Review).where(Review.target_key == key, Review.user_id == user.id))
    if not r:
        raise HTTPException(404, "You haven't reviewed this")
    db.delete(r)
    db.commit()
    return {"ok": True}


def _club_for_view(db, slug, user) -> Club:
    club = get_club_or_404(db, slug)
    if not can_view_club(db, club, user, get_membership(db, club.id, user.id if user else None)):
        raise HTTPException(404, "Club not found")
    return club


def _event_for_view(db, slug, user) -> Event:
    e = db.scalar(select(Event).where(Event.slug == slug))
    if not e or not can_view_event(e, user, get_membership(db, e.club_id, user.id if user else None)):
        raise HTTPException(404, "Event not found")
    return e


@router.get("/clubs/{slug}/reviews")
def club_reviews(slug: str, limit: int = 20, offset: int = 0, user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    club = _club_for_view(db, slug, user)
    return _list(db, f"club:{club.id}", user, limit, offset, lambda: _club_eligible(db, club, user))


@router.put("/clubs/{slug}/reviews/mine", dependencies=[Depends(rate_limit("review", 20, 3600))])
def put_club_review(slug: str, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    club = _club_for_view(db, slug, user)
    ok, reason = _club_eligible(db, club, user)
    if not ok:
        raise HTTPException(403, reason)
    return _upsert(db, f"club:{club.id}", "club", club, None, user, body)


@router.delete("/clubs/{slug}/reviews/mine")
def delete_club_review(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _delete(db, f"club:{_club_for_view(db, slug, user).id}", user)


@router.get("/events/{slug}/reviews")
def event_reviews(slug: str, limit: int = 20, offset: int = 0, user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    e = _event_for_view(db, slug, user)
    return _list(db, f"event:{e.id}", user, limit, offset, lambda: _event_eligible(db, e, user))


@router.put("/events/{slug}/reviews/mine", dependencies=[Depends(rate_limit("review", 20, 3600))])
def put_event_review(slug: str, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = _event_for_view(db, slug, user)
    ok, reason = _event_eligible(db, e, user)
    if not ok:
        raise HTTPException(403, reason)
    return _upsert(db, f"event:{e.id}", "event", e.club, e, user, body)


@router.delete("/events/{slug}/reviews/mine")
def delete_event_review(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _delete(db, f"event:{_event_for_view(db, slug, user).id}", user)


class ReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=1000)


@router.put("/clubs/{slug}/reviews/{review_id}/reply")
def reply(review_id: UUID, body: ReplyIn, ctx: ClubCtx = Depends(club_perm("club.settings")), db: Session = Depends(get_db)):
    r = db.scalar(select(Review).where(Review.id == review_id, Review.club_id == ctx.club.id))
    if not r:
        raise HTTPException(404, "Review not found")
    r.reply, r.reply_at = body.reply.strip(), utcnow()
    audit(db, ctx.club.id, ctx.user.id, "review.replied", str(r.id))
    db.commit()
    return review_out(r)


@router.post("/reviews/{review_id}/report", dependencies=[Depends(rate_limit("report", 30, 3600))])
def report(review_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Review, review_id)
    if not r or r.status != "published":
        raise HTTPException(404, "Review not found")
    if r.user_id == user.id:
        raise HTTPException(400, "You can't report your own review")
    if str(user.id) in (r.reporters or []):
        raise HTTPException(409, "Already reported")
    r.reporters = [*(r.reporters or []), str(user.id)]  # reassign so the JSON change is tracked
    db.commit()
    return {"ok": True}  # reports queue for moderators; nothing auto-hides, so it can't be brigaded


@router.get("/reviews/featured")
def featured(db: Session = Depends(get_db)):
    rows = db.scalars(select(Review).join(Club, Club.id == Review.club_id).where(
        Review.target_type == "club", Review.status == "published", Review.rating >= 4, func.length(Review.body) >= 40,
        Club.visibility == "public").order_by(Review.created_at.desc()).limit(6)).unique().all()
    return [review_out(r) for r in rows]
