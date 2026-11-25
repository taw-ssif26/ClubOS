from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Review


def rating_map(db: Session, keys: list[str]) -> dict[str, dict]:
    if not keys:
        return {}
    rows = db.execute(select(Review.target_key, func.avg(Review.rating), func.count()).where(
        Review.target_key.in_(keys), Review.status == "published").group_by(Review.target_key)).all()
    return {k: {"average": round(float(a), 2), "count": n} for k, a, n in rows}


def rating_for(db: Session, key: str) -> dict:
    return rating_map(db, [key]).get(key, {"average": None, "count": 0})
