"""Club leaderboard. Optional per club; points are assigned by people with `points.manage`; everything stays inside the club."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ClubCtx, club_perm
from ..models import Membership, PointEntry, User, utcnow
from ..permissions import has_perm
from ..ratelimit import rate_limit
from ..services.core import audit, iso, notify

router = APIRouter(prefix="/clubs/{slug}/leaderboard", tags=["leaderboard"])
DHAKA = timedelta(hours=6)


def _on(ctx: ClubCtx):
    if not ctx.club.leaderboard_enabled:
        raise HTTPException(404, {"code": "leaderboard_off", "message": "This club has not turned on a leaderboard"})


def _month_start() -> datetime:
    now = utcnow() + DHAKA
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc) - DHAKA


@router.get("")
def board(period: Literal["all", "month"] = "all", limit: int = 50, ctx: ClubCtx = Depends(club_perm(None)), db: Session = Depends(get_db)):
    """Visible to active members of THIS club only (club_perm already hides the club from everyone else)."""
    _on(ctx)
    q = select(PointEntry.user_id, func.sum(PointEntry.points)).where(PointEntry.club_id == ctx.club.id).group_by(PointEntry.user_id)
    if period == "month":
        q = q.where(PointEntry.created_at >= _month_start())
    totals = {uid: int(t) for uid, t in db.execute(q).all()}
    members = db.scalars(select(Membership).where(Membership.club_id == ctx.club.id, Membership.status == "active")).unique().all()
    rows = sorted(((m, totals[m.user_id]) for m in members if m.user_id in totals), key=lambda t: (-t[1], t[0].user.full_name.lower()))
    ranked, last, last_rank = [], None, 0
    for i, (m, pts) in enumerate(rows, start=1):
        last_rank = last_rank if pts == last else i          # ties share a rank (1, 2, 2, 4)
        last = pts
        ranked.append({"rank": last_rank, "points": pts, "user": {"name": m.user.full_name, "username": m.user.username}, "is_me": m.user_id == ctx.user.id})
    me = next((r for r in ranked if r["is_me"]), None)
    return {"period": period, "entries": ranked[:min(limit, 100)], "me": me, "participants": len(ranked),
            "can_award": has_perm(ctx.membership, "points.manage")}


@router.get("/history")
def history(username: str | None = None, ctx: ClubCtx = Depends(club_perm(None)), db: Session = Depends(get_db)):
    """Your own point history; people with points.manage can open anyone's. Reasons (incl. deductions) are not shown to other members."""
    _on(ctx)
    target = ctx.user
    if username and username != ctx.user.username:
        if not has_perm(ctx.membership, "points.manage"):
            raise HTTPException(403, "You can only see your own point history")
        target = db.scalar(select(User).where(User.username == username))
        if not target:
            raise HTTPException(404, "Member not found")
    rows = db.scalars(select(PointEntry).where(PointEntry.club_id == ctx.club.id, PointEntry.user_id == target.id)
                      .order_by(PointEntry.created_at.desc()).limit(100)).unique().all()
    return [{"id": str(r.id), "points": r.points, "reason": r.reason, "by": r.awarder.full_name, "at": iso(r.created_at)} for r in rows]


@router.get("/recent")
def recent(ctx: ClubCtx = Depends(club_perm("points.manage")), db: Session = Depends(get_db)):
    _on(ctx)
    rows = db.scalars(select(PointEntry).where(PointEntry.club_id == ctx.club.id).order_by(PointEntry.created_at.desc()).limit(50)).unique().all()
    return [{"id": str(r.id), "points": r.points, "reason": r.reason, "to": r.recipient.full_name, "username": r.recipient.username,
             "by": r.awarder.full_name, "at": iso(r.created_at)} for r in rows]


class AwardIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    points: int = Field(ge=-500, le=500)
    reason: str = Field(min_length=3, max_length=200)


@router.post("/awards", status_code=201, dependencies=[Depends(rate_limit("points", 120, 3600))])
def award(body: AwardIn, ctx: ClubCtx = Depends(club_perm("points.manage")), db: Session = Depends(get_db)):
    _on(ctx)
    if body.points == 0:
        raise HTTPException(422, "Points cannot be zero")
    target = db.scalar(select(User).where(User.username == body.username))
    m = db.scalar(select(Membership).where(Membership.club_id == ctx.club.id, Membership.user_id == target.id)) if target else None
    if not m or m.status != "active":
        raise HTTPException(404, "That person is not an active member of this club")
    if target.id == ctx.user.id:
        raise HTTPException(403, "You can't award points to yourself. Ask another admin.")  # conflict of interest, applies to Owners too
    db.add(PointEntry(club_id=ctx.club.id, user_id=target.id, points=body.points, reason=body.reason.strip(), awarded_by=ctx.user.id))
    notify(db, target.id, f"{'+' if body.points > 0 else ''}{body.points} points in {ctx.club.name}", body.reason.strip(), f"/c/{ctx.club.slug}/leaderboard")
    audit(db, ctx.club.id, ctx.user.id, "points.awarded", target.username, {"points": body.points, "reason": body.reason.strip()[:80]})
    db.commit()
    return {"ok": True}


@router.delete("/awards/{entry_id}")
def revoke(entry_id: UUID, ctx: ClubCtx = Depends(club_perm("points.manage")), db: Session = Depends(get_db)):
    _on(ctx)
    e = db.scalar(select(PointEntry).where(PointEntry.id == entry_id, PointEntry.club_id == ctx.club.id))
    if not e:
        raise HTTPException(404, "Entry not found")
    audit(db, ctx.club.id, ctx.user.id, "points.revoked", e.recipient.username, {"points": e.points, "reason": e.reason[:80]})
    db.delete(e)
    db.commit()
    return {"ok": True}
