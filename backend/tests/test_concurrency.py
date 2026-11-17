"""Needs real PostgreSQL (SQLite ignores row locks). Run with DATABASE_URL=postgresql://..."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import db_set_plan, make_user

pytestmark = pytest.mark.skipif(not os.environ["DATABASE_URL"].startswith("postgres"), reason="needs PostgreSQL")


def _race(plan: str, slug: str):
    owner = make_user(f"{slug.replace('-', '_')}_owner")
    owner.post("/clubs", json={"name": slug.title(), "slug": slug})
    db_set_plan(slug, plan)
    start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    ev = owner.post(f"/clubs/{slug}/events", json={"title": "Race day", "starts_at": start, "capacity": 3, "status": "published"}).json()["slug"]
    users = [make_user(f"{slug.replace('-', '_')}_r{i}") for i in range(12)]
    with ThreadPoolExecutor(max_workers=12) as ex:
        return list(ex.map(lambda u: u.post(f"/events/{ev}/register", json={"answers": {}}), users))


def test_pro_capacity_never_oversold_rest_waitlisted():
    res = _race("pro", "race-pro")
    statuses = [r.json()["status"] for r in res]
    assert statuses.count("confirmed") == 3 and statuses.count("waitlisted") == 9


def test_free_capacity_never_oversold_rest_rejected():
    res = _race("free", "race-free")
    assert sorted(r.status_code for r in res) == [201] * 3 + [409] * 9


def test_member_limit_is_never_overshot():
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Membership, Plan
    owner = make_user("lim_owner")
    owner.post("/clubs", json={"name": "Lim Club", "slug": "lim-club", "join_policy": "open"})
    with SessionLocal() as db:
        p = db.scalars(select(Plan).where(Plan.key == "free")).one()
        p.limits = {**p.limits, "members": 4}   # owner + 3
        db.commit()
    try:
        users = [make_user(f"lim_r{i}") for i in range(12)]
        with ThreadPoolExecutor(max_workers=12) as ex:
            codes = list(ex.map(lambda u: u.post("/clubs/lim-club/join", json={}).status_code, users))
        with SessionLocal() as db:
            active = len(db.scalars(select(Membership).where(Membership.status == "active")).unique().all())
        assert codes.count(200) == 3 and codes.count(402) == 9
    finally:
        with SessionLocal() as db:
            p = db.scalars(select(Plan).where(Plan.key == "free")).one()
            p.limits = {**p.limits, "members": 100}
            db.commit()
