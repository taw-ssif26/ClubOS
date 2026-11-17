import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club
from tests.conftest import db_set_plan, make_admin, make_user

FUT = lambda d: (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()  # noqa: E731
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _club(owner, slug):
    assert owner.post("/clubs", json={"name": slug.title(), "slug": slug, "join_policy": "open"}).status_code == 201


def test_free_plan_is_generous_but_bounded():
    o = make_user("fp_owner")
    _club(o, "free-club")
    # basic features work on Free
    assert o.post("/clubs/free-club/posts", json={"title": "Hi", "body": "x", "status": "published"}).status_code == 201
    assert o.patch("/clubs/free-club", json={"theme": {"preset": "editorial", "primary": "#0d2a21"}}).status_code == 200
    # ...advanced customization is Pro
    for theme in ({"preset": "bold"}, {"secondary": "#112233"}, {"font": "mono"}, {"hide_branding": True}):
        r = o.patch("/clubs/free-club", json={"theme": theme})
        assert r.status_code == 402 and r.json()["detail"]["code"] == "upgrade_required", theme
    # bulk email + conditional logic are Pro
    assert o.post("/clubs/free-club/communications", json={"subject": "x", "body": "y", "audience": {"type": "all_members"}}).json()["detail"]["feature"] == "bulk_email"
    cond = [{"id": "a", "type": "radio", "label": "A", "options": ["y", "n"]}, {"id": "b", "type": "text", "label": "B", "show_if": {"field": "a", "equals": "y"}}]
    assert o.post("/clubs/free-club/events", json={"title": "Cond", "starts_at": FUT(5), "registration_fields": cond}).status_code == 402
    # custom fields (no conditions) are free
    plain = [{"id": "a", "type": "text", "label": "A"}]
    assert o.post("/clubs/free-club/events", json={"title": "Plain", "starts_at": FUT(5), "status": "published", "registration_fields": plain}).status_code == 201
    # advanced analytics gated, basic available
    an = o.get("/clubs/free-club/analytics").json()
    assert an["basic"]["members"] == 1 and an["advanced"] is None and an["upgrade_required"] == "advanced_analytics"

    # 5 active events max; drafts don't count; past events don't count
    for i in range(4):
        assert o.post("/clubs/free-club/events", json={"title": f"Event {i}", "starts_at": FUT(6 + i), "status": "published"}).status_code == 201
    r = o.post("/clubs/free-club/events", json={"title": "Sixth", "starts_at": FUT(20), "status": "published"})
    assert r.status_code == 402 and r.json()["detail"]["code"] == "limit_reached" and r.json()["detail"]["max"] == 5
    draft = o.post("/clubs/free-club/events", json={"title": "Draft ok", "starts_at": FUT(21)})
    assert draft.status_code == 201
    assert o.patch(f"/events/{draft.json()['slug']}", json={"status": "published"}).status_code == 402  # publishing is what counts

    # waitlist is Pro: a full event on Free simply closes
    cap = o.post("/clubs/free-club/events", json={"title": "Tiny", "starts_at": FUT(3), "capacity": 1}).json()["slug"]
    # (free club is at 5 active events, so publish by cancelling one first)
    first = next(e["slug"] for e in o.get("/clubs/free-club/events").json() if e["status"] == "published")
    o.patch(f"/events/{first}", json={"status": "cancelled"})
    assert o.patch(f"/events/{cap}", json={"status": "published"}).status_code == 200
    a, b = make_user("fp_a"), make_user("fp_b")
    assert a.post(f"/events/{cap}/register", json={"answers": {}}).json()["status"] == "confirmed"
    r = b.post(f"/events/{cap}/register", json={"answers": {}})
    assert r.status_code == 409 and "full" in r.json()["detail"]

    # admin seats: owner + 2 = 3 on Free
    for n in ("fp_s1", "fp_s2", "fp_s3"):
        u = make_user(n)
        assert u.post("/clubs/free-club/join", json={}).json()["status"] == "active"
    roles = {r["name"]: r["id"] for r in o.get("/clubs/free-club/roles").json()}
    mids = {m["user"]["username"]: m["id"] for m in o.get("/clubs/free-club/members").json()}
    assert o.patch(f"/clubs/free-club/members/{mids['fp_s1']}", json={"role_id": roles["Administrator"]}).status_code == 200
    assert o.patch(f"/clubs/free-club/members/{mids['fp_s2']}", json={"role_id": roles["Executive"]}).status_code == 200
    r = o.patch(f"/clubs/free-club/members/{mids['fp_s3']}", json={"role_id": roles["Administrator"]})
    assert r.status_code == 402 and r.json()["detail"]["limit"] == "admins"
    # volunteers/members don't take admin seats
    assert o.patch(f"/clubs/free-club/members/{mids['fp_s3']}", json={"role_id": roles["Volunteer"]}).status_code == 200
    u = o.get("/clubs/free-club/usage").json()
    assert u["usage"]["admins"] == 3 and u["limits"]["members"] == 100


def test_member_limit_and_pro_unlocks_everything():
    o = make_user("ml_owner")
    _club(o, "limit-club")
    with SessionLocal() as db:  # shrink Free to 2 members via the editable plan table
        from app.models import Plan
        p = db.scalars(select(Plan).where(Plan.key == "free")).one()
        p.limits = {**p.limits, "members": 2}
        db.commit()
    assert make_user("ml_a").post("/clubs/limit-club/join", json={}).status_code == 200
    r = make_user("ml_b").post("/clubs/limit-club/join", json={})
    assert r.status_code == 402 and r.json()["detail"]["limit"] == "members"
    db_set_plan("limit-club", "pro")
    assert make_user("ml_c").post("/clubs/limit-club/join", json={}).status_code == 200
    assert o.patch("/clubs/limit-club", json={"theme": {"preset": "bold", "secondary": "#112233", "font": "mono", "hide_branding": True}}).status_code == 200
    assert o.get("/clubs/limit-club").json()["show_branding"] is False
    an = o.get("/clubs/limit-club/analytics").json()
    assert an["advanced"]["member_growth"] and an["advanced"]["retention"] == 1.0
    with SessionLocal() as db:  # restore
        from app.models import Plan
        p = db.scalars(select(Plan).where(Plan.key == "free")).one()
        p.limits = {**p.limits, "members": 100}
        db.commit()


def test_plan_expiry_falls_back_to_free():
    o = make_user("ex_owner")
    _club(o, "expiring")
    db_set_plan("expiring", "pro")
    assert o.get("/clubs/expiring/usage").json()["effective_plan"] == "pro"
    with SessionLocal() as db:
        c = db.scalars(select(Club).where(Club.slug == "expiring")).one()
        c.plan_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    u = o.get("/clubs/expiring/usage").json()
    assert u["plan"] == "pro" and u["effective_plan"] == "free"           # data kept, entitlements dropped
    assert o.post("/clubs/expiring/communications", json={"subject": "x", "body": "y", "audience": {"type": "all_members"}}).status_code == 402


def test_upgrade_request_flow():
    o, admin = make_user("up_owner"), make_user("up_admin")
    make_admin(admin, "up_admin")
    _club(o, "upgrade-me")
    assert o.post("/clubs/upgrade-me/upgrade-requests", json={"plan_key": "free", "contact": "01700000000"}).status_code == 422
    assert o.post("/clubs/upgrade-me/upgrade-requests", json={"plan_key": "pro", "months": 3, "contact": "01700000000"}).status_code == 201
    assert o.post("/clubs/upgrade-me/upgrade-requests", json={"plan_key": "pro", "contact": "01700000000"}).status_code == 409
    assert any("Upgrade request" in n["title"] for n in admin.get("/notifications").json())
    assert o.get("/admin/upgrade-requests").status_code == 403
    rid = next(r["id"] for r in admin.get("/admin/upgrade-requests").json() if r["club"]["slug"] == "upgrade-me")
    assert admin.post(f"/admin/upgrade-requests/{rid}/approve").status_code == 200
    u = o.get("/clubs/upgrade-me/usage").json()
    assert u["effective_plan"] == "pro" and u["expires_at"]
    # renewal extends rather than resets
    first = u["expires_at"]
    assert admin.post("/admin/clubs/upgrade-me/plan", json={"plan": "pro", "months": 1}).status_code == 200
    assert o.get("/clubs/upgrade-me/usage").json()["expires_at"] > first


def test_uploads_are_validated_and_metered():
    o = make_user("up2_owner")
    _club(o, "pics")
    ok = o.post("/clubs/pics/uploads", files={"file": ("logo.png", io.BytesIO(PNG), "image/png")})
    assert ok.status_code == 201, ok.text
    url = ok.json()["url"]
    assert o.get("/clubs/pics/uploads").json()["used_bytes"] == len(PNG)
    assert o.patch("/clubs/pics", json={"logo_url": url}).status_code == 200
    assert o.patch("/clubs/pics", json={"logo_url": "javascript:alert(1)"}).status_code == 422
    assert o.get(url).status_code == 200 and o.get(url).headers["x-content-type-options"] == "nosniff"
    # the bytes decide, not the filename or declared type
    assert o.post("/clubs/pics/uploads", files={"file": ("a.png", io.BytesIO(b"<svg onload=alert(1)>"), "image/png")}).status_code == 415
    assert o.post("/clubs/pics/uploads", files={"file": ("a.png", io.BytesIO(b"<?php ?>"), "image/png")}).status_code == 415
    # quota
    with SessionLocal() as db:
        from app.models import Plan
        p = db.scalars(select(Plan).where(Plan.key == "free")).one()
        p.limits = {**p.limits, "storage_mb": 0}
        db.commit()
    r = o.post("/clubs/pics/uploads", files={"file": ("b.png", io.BytesIO(PNG), "image/png")})
    assert r.status_code == 402 and r.json()["detail"]["limit"] == "storage_mb"
    with SessionLocal() as db:
        p = db.scalars(select(Plan).where(Plan.key == "free")).one()
        p.limits = {**p.limits, "storage_mb": 500}
        db.commit()
    assert o.delete(f"/clubs/pics/uploads/{ok.json()['id']}").status_code == 200
    assert make_user("up2_x").post("/clubs/pics/uploads", files={"file": ("c.png", io.BytesIO(PNG), "image/png")}).status_code == 404


def test_calendar_feed_and_member_export():
    o = make_user("cal_owner")
    _club(o, "cal-club")
    o.post("/clubs/cal-club/events", json={"title": "Demo, Day; One", "starts_at": FUT(4), "venue": "Hall", "status": "published"})
    r = o.get("/clubs/cal-club/calendar.ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in r.text and "SUMMARY:Demo\\, Day\\; One" in r.text
    csv_text = o.get("/clubs/cal-club/members.csv").text
    assert csv_text.startswith("name,username,email") and "cal_owner" in csv_text
