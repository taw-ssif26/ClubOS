"""Public, cacheable site data: page copy, pricing and offers. All of it is editable from the super admin."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Offer, Plan, SiteContent, utcnow

router = APIRouter(tags=["site"])


def active_offers(db: Session, placements: tuple[str, ...]) -> list[Offer]:
    now = utcnow()
    return db.scalars(select(Offer).where(
        Offer.active.is_(True), Offer.placement.in_(placements),
        or_(Offer.starts_at.is_(None), Offer.starts_at <= now), or_(Offer.ends_at.is_(None), Offer.ends_at >= now))
        .order_by(Offer.created_at.desc())).all()


def offer_out(o: Offer) -> dict:
    return {"id": str(o.id), "title": o.title, "body": o.body, "badge": o.badge, "cta_label": o.cta_label, "cta_url": o.cta_url,
            "plan_key": o.plan_key, "discount_percent": o.discount_percent, "placement": o.placement,
            "starts_at": o.starts_at and o.starts_at.isoformat(), "ends_at": o.ends_at and o.ends_at.isoformat(), "active": o.active}


def plan_out(p: Plan) -> dict:
    return {"key": p.key, "name": p.name, "tagline": p.tagline, "price_monthly": p.price_monthly, "price_label": p.price_label,
            "cta_label": p.cta_label, "limits": p.limits, "features": p.features, "highlighted": p.highlighted,
            "visible": p.visible, "sort": p.sort}


@router.get("/content")
def content(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=15"
    return {c.key: c.value for c in db.scalars(select(SiteContent))}


@router.get("/pricing")
def pricing(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=15"
    offers = active_offers(db, ("pricing", "both"))
    out = []
    for p in db.scalars(select(Plan).where(Plan.visible.is_(True)).order_by(Plan.sort)):
        d = plan_out(p)
        best = max((o for o in offers if o.plan_key == p.key and o.discount_percent), key=lambda o: o.discount_percent, default=None)
        d["offer"] = offer_out(best) if best else None
        d["discounted_price"] = round(p.price_monthly * (100 - best.discount_percent) / 100) if best and p.price_monthly else None
        out.append(d)
    return {"plans": out}


@router.get("/offers/active")
def banner_offers(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "public, max-age=15"
    return [offer_out(o) for o in active_offers(db, ("banner", "both"))]
