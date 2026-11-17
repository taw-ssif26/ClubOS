from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import db_set_plan, make_admin, make_user

FUT = lambda d: (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()  # noqa: E731


def test_reviews_only_from_real_participants():
    o, m1, m2, out = (make_user(n) for n in ("rv_owner", "rv_m1", "rv_m2", "rv_out"))
    assert o.post("/clubs", json={"name": "Review Club", "slug": "review-club", "join_policy": "open"}).status_code == 201
    for u in (m1, m2):
        assert u.post("/clubs/review-club/join", json={}).status_code == 200
    # eligibility
    assert out.put("/clubs/review-club/reviews/mine", json={"rating": 5}).status_code == 403       # never a member
    assert o.put("/clubs/review-club/reviews/mine", json={"rating": 5}).status_code == 403          # can't review yourself
    assert m1.put("/clubs/review-club/reviews/mine", json={"rating": 6}).status_code == 422
    r = m1.put("/clubs/review-club/reviews/mine", json={"rating": 5, "title": "Great", "body": "Well run and genuinely welcoming to new people."})
    assert r.status_code == 200
    assert m1.put("/clubs/review-club/reviews/mine", json={"rating": 4, "body": "Updated opinion that is long enough to feature."}).status_code == 200  # edit, not duplicate
    m2.put("/clubs/review-club/reviews/mine", json={"rating": 2, "body": "Meh"})
    data = TestClient(app).get("/clubs/review-club/reviews").json()
    assert data["summary"]["count"] == 2 and data["summary"]["average"] == 3.0 and data["summary"]["histogram"]["4"] == 1
    assert out.get("/clubs/review-club/reviews").json()["can_review"] is False
    assert m1.get("/clubs/review-club/reviews").json()["mine"]["rating"] == 4
    assert TestClient(app).get("/clubs/review-club").json()["rating"]["average"] == 3.0
    assert any(c["slug"] == "review-club" and c["rating"]["count"] == 2 for c in TestClient(app).get("/discover/clubs").json())

    # club reply + report + moderation
    rid = data["items"][0]["id"]
    assert m1.put(f"/clubs/review-club/reviews/{rid}/reply", json={"reply": "thanks"}).status_code == 403
    assert o.put(f"/clubs/review-club/reviews/{rid}/reply", json={"reply": "Thank you!"}).json()["reply"] == "Thank you!"
    assert out.post(f"/reviews/{rid}/report").status_code == 200
    assert out.post(f"/reviews/{rid}/report").status_code == 409
    mine_id = m1.get("/clubs/review-club/reviews").json()["mine"]["id"]
    assert m1.post(f"/reviews/{mine_id}/report").status_code == 400
    admin = make_user("rv_admin")
    make_admin(admin, "rv_admin")
    assert o.post(f"/admin/reviews/{rid}/hide").status_code == 403
    assert admin.get("/admin/reviews?reported=true").json()[0]["reports"] == 1
    assert admin.post(f"/admin/reviews/{rid}/hide").status_code == 200
    assert TestClient(app).get("/clubs/review-club/reviews").json()["summary"]["count"] == 1
    assert len(TestClient(app).get("/reviews/featured").json()) == 1  # only >=4 stars with a real body

    # delete own
    assert m1.delete("/clubs/review-club/reviews/mine").status_code == 200
    assert m1.delete("/clubs/review-club/reviews/mine").status_code == 404


def test_event_reviews_require_check_in():
    o, att, noshow = make_user("er_owner"), make_user("er_att"), make_user("er_no")
    o.post("/clubs", json={"name": "Event Rev", "slug": "event-rev"})
    db_set_plan("event-rev", "pro")
    slug = o.post("/clubs/event-rev/events", json={"title": "Past Fest", "starts_at": FUT(1), "status": "published"}).json()["slug"]
    for u in (att, noshow):
        u.post(f"/events/{slug}/register", json={"answers": {}})
    code = att.get(f"/events/{slug}").json()["my_registration"]["ticket_code"]
    assert o.post(f"/events/{slug}/checkin", json={"ticket_code": code}).status_code == 200
    assert att.put(f"/events/{slug}/reviews/mine", json={"rating": 5}).status_code == 403          # event hasn't started yet
    # move the event into the past
    from app.db import SessionLocal
    from app.models import Event
    from sqlalchemy import select
    with SessionLocal() as db:
        ev = db.scalars(select(Event).where(Event.slug == slug)).one()
        ev.starts_at = datetime.now(timezone.utc) - timedelta(hours=3)
        db.commit()
    assert noshow.put(f"/events/{slug}/reviews/mine", json={"rating": 1}).status_code == 403       # registered but never checked in
    assert att.put(f"/events/{slug}/reviews/mine", json={"rating": 5, "body": "Loved it"}).status_code == 200
    assert TestClient(app).get(f"/events/{slug}").json()["rating"] == {"average": 5.0, "count": 1}


def test_cms_pricing_offers_all_editable():
    admin, user = make_user("cms_admin"), make_user("cms_user")
    make_admin(admin, "cms_admin")
    anon = TestClient(app)
    c = anon.get("/content").json()
    assert c["home.hero"]["title"] and c["pricing.page"]["faq"] and c["nav"]["links"]
    assert user.put("/admin/content/home.hero", json={"value": {"title": "x"}}).status_code == 403
    assert admin.put("/admin/content/not.a.key", json={"value": {}}).status_code == 404
    hero = {**c["home.hero"], "title": "Edited from super admin"}
    assert admin.put("/admin/content/home.hero", json={"value": hero}).status_code == 200
    assert anon.get("/content").json()["home.hero"]["title"] == "Edited from super admin"
    assert admin.post("/admin/content/home.hero/reset").status_code == 200
    assert anon.get("/content").json()["home.hero"]["title"] != "Edited from super admin"

    # pricing: edit a plan, see it publicly, and limits take effect immediately
    plans = {p["key"]: p for p in anon.get("/pricing").json()["plans"]}
    assert set(plans) == {"free", "pro", "organization", "enterprise"} and plans["free"]["price_monthly"] == 0
    pro = plans["pro"]
    body = {k: pro[k] for k in ("name", "tagline", "price_monthly", "price_label", "cta_label", "limits", "features", "highlighted", "visible", "sort")}
    body["price_monthly"], body["price_label"] = 999, "৳999"
    assert admin.put("/admin/plans/pro", json=body).status_code == 200
    assert {p["key"]: p for p in anon.get("/pricing").json()["plans"]}["pro"]["price_monthly"] == 999
    assert admin.put("/admin/plans/pro", json={**body, "limits": {**body["limits"], "members": -5}}).status_code == 422
    # offers: appear in the banner and discount the plan, expire on schedule
    assert anon.get("/offers/active").json() == []
    r = admin.post("/admin/offers", json={"title": "Launch month", "body": "30% off Pro", "badge": "Launch", "plan_key": "pro", "discount_percent": 30, "placement": "both", "cta_url": "/pricing"})
    assert r.status_code == 201
    assert anon.get("/offers/active").json()[0]["title"] == "Launch month"
    assert {p["key"]: p for p in anon.get("/pricing").json()["plans"]}["pro"]["discounted_price"] == 699
    oid = r.json()["id"]
    assert admin.put(f"/admin/offers/{oid}", json={"title": "Ended", "placement": "both", "ends_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}).status_code == 200
    assert anon.get("/offers/active").json() == []
    assert admin.post("/admin/offers", json={"title": "bad", "cta_url": "javascript:alert(1)"}).status_code == 422
    assert admin.delete(f"/admin/offers/{oid}").status_code == 200
    admin.put("/admin/plans/pro", json={**body, "price_monthly": 800, "price_label": "৳800"})
    # user management
    victim = make_user("cms_victim")
    uid = next(u["id"] for u in admin.get("/admin/users?q=cms_victim").json())
    assert admin.post(f"/admin/users/{uid}/suspend").status_code == 200
    assert victim.get("/users/me").status_code == 401
    assert any(a["action"] == "content.updated" for a in admin.get("/admin/audit").json())


def test_csrf_origin_check():
    u = make_user("csrf_user")
    r = u.post("/notifications/read-all", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert u.post("/notifications/read-all", headers={"Origin": "http://localhost:3000"}).status_code == 200
