"""Locations, event phases, post attachments, club approval, leaderboard."""
import io
import os
import zipfile
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import PointEntry, Role, Upload
from app.seed import sync_system_roles
from tests.conftest import make_admin, make_user

PNG = b"\x89PNG\r\n\x1a\n" + b"2" * 64
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
NOW = lambda h=0: (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()  # noqa: E731


def docx_bytes(root="word/") -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(f"{root}document.xml", "<doc/>")
    return b.getvalue()


def mk(owner, slug, **extra):
    r = owner.post("/clubs", json={"name": slug.replace("-", " ").title(), "slug": slug, "join_policy": "open",
                                   "description": "A club that does interesting things together.", **extra})
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ locations
def test_places_and_user_location_privacy():
    places = TestClient(app).get("/places").json()
    assert len(places) == 80 and {"id": "dhaka"}.items() <= {k: v for k, v in next(p for p in places if p["id"] == "dhaka").items()}.items()
    assert all(20.5 <= p["lat"] <= 26.7 and 88 <= p["lng"] <= 92.7 for p in places)
    u = make_user("loc_user")
    assert u.patch("/users/me", json={"place": "atlantis"}).status_code == 422
    assert u.patch("/users/me", json={"latitude": 23.8}).status_code == 422                   # both or neither
    r = u.patch("/users/me", json={"latitude": 23.812345, "longitude": 90.412987}).json()
    assert (r["latitude"], r["longitude"]) == (23.81, 90.41)                                  # never store a precise position
    assert u.patch("/users/me", json={"place": "dhanmondi"}).json()["place_name"] == "Dhanmondi, Dhaka"
    assert "latitude" not in make_user("loc_viewer").get("/users/loc_user").json()            # never exposed to others
    u.patch("/users/me", json={"profile_public": True})
    pub = TestClient(app).get("/users/loc_user").json()
    assert "latitude" not in pub and "place" not in pub
    assert u.get("/users/me/export").json()["profile"]["location"]["place"] == "dhanmondi"
    assert u.patch("/users/me", json={"clear_location": True}).json()["place"] is None


def test_clubs_nearest_ranking_filters_and_online():
    o = make_user("near_owner")
    mk(o, "near-dhanmondi", place="dhanmondi")
    mk(o, "near-sylhet", place="sylhet")
    mk(o, "near-chattogram", place="chattogram", location_mode="hybrid")
    mk(o, "near-online", location_mode="online")
    mk(o, "near-noplace")
    me = make_user("near_me")
    me.patch("/users/me", json={"place": "dhaka"})
    anon = TestClient(app)
    ids = lambda r: [c["slug"] for c in r if c["slug"].startswith("near-")]  # noqa: E731
    order = ids(me.get("/discover/clubs?near=true&sort=nearest&limit=50").json())
    assert order[:3] == ["near-dhanmondi", "near-sylhet", "near-chattogram"]                  # by distance
    assert set(order[3:]) == {"near-online", "near-noplace"}                                  # no position: after the nearby ones
    dist = {c["slug"]: c["distance_km"] for c in me.get("/discover/clubs?near=true&sort=nearest&limit=50").json() if c["slug"].startswith("near-")}
    assert 5 < dist["near-dhanmondi"] < 12 and 180 < dist["near-sylhet"] < 200 and dist["near-online"] is None
    assert "near-chattogram" not in ids(me.get("/discover/clubs?near=true&sort=nearest&max_km=200&limit=50").json())
    assert ids(anon.get("/discover/clubs?mode=online&limit=50").json()) == ["near-online"]
    assert ids(anon.get("/discover/clubs?place=chattogram&limit=50").json()) == ["near-chattogram"]
    chat = anon.get("/discover/clubs?lat=22.35&lng=91.78&sort=nearest&limit=50").json()          # explicit coordinates, no account
    assert ids(chat)[0] == "near-chattogram"
    assert anon.get("/discover/clubs?lat=95&lng=10&sort=nearest").status_code == 422
    # a club can change place and its coordinates follow
    assert o.patch("/clubs/near-noplace", json={"place": "rajshahi"}).json()["location"]["latitude"] == 24.3745
    assert o.patch("/clubs/near-noplace", json={"location_mode": "online"}).json()["location"]["place"] is None


def test_event_location_phases_and_join_link():
    o, att, out = make_user("ph_owner"), make_user("ph_att"), make_user("ph_out")
    mk(o, "phase-club")
    mkev = lambda title, start, end, **x: o.post("/clubs/phase-club/events", json={"title": title, "starts_at": start, "ends_at": end, "status": "published", **x}).json()  # noqa: E731
    past = mkev("Past Meetup", NOW(-30), NOW(-27))
    live = mkev("Live Now Meetup", NOW(-1), NOW(2), location_mode="hybrid", place="gazipur", online_url="https://meet.example.com/abc")
    soon = mkev("Soon Meetup", NOW(48), None, location_mode="online", online_url="https://meet.example.com/soon")
    noend = mkev("Just Started", NOW(-1), None)                                                   # no end time: ongoing for 3 hours
    assert {e["slug"]: e["phase"] for e in [past, live, soon, noend]} == {past["slug"]: "past", live["slug"]: "ongoing", soon["slug"]: "upcoming", noend["slug"]: "ongoing"}
    page = TestClient(app).get("/public/clubs/phase-club").json()
    assert [e["title"] for e in page["events"]][:2] == ["Live Now Meetup", "Just Started"] or {e["title"] for e in page["events"]} == {"Live Now Meetup", "Just Started", "Soon Meetup"}
    assert {e["title"] for e in page["events"]} == {"Live Now Meetup", "Just Started", "Soon Meetup"}
    assert [e["title"] for e in page["past_events"]] == ["Past Meetup"]
    disc = [e["title"] for e in TestClient(app).get("/discover/events?limit=50").json()]
    assert "Live Now Meetup" in disc and "Past Meetup" not in disc                                # ongoing is discoverable, past is not
    assert live["location"]["place_name"] == "Gazipur" and live["location"]["latitude"] == 23.9999 and soon["location"]["place"] is None
    assert o.post("/clubs/phase-club/events", json={"title": "Bad Place", "starts_at": NOW(5), "place": "mars"}).status_code == 422
    # the join link is for people who are in, never public
    assert "online_url" not in TestClient(app).get(f"/events/{live['slug']}").json()
    assert "online_url" not in out.get(f"/events/{live['slug']}").json()
    assert o.get(f"/events/{live['slug']}").json()["online_url"] == "https://meet.example.com/abc"
    assert att.post(f"/events/{soon['slug']}/register", json={"answers": {}}).status_code == 201
    assert att.get(f"/events/{soon['slug']}").json()["online_url"] == "https://meet.example.com/soon"


# ------------------------------------------------------------------ attachments
def up(c, slug, name, data, ctype="application/octet-stream", only="any"):
    return c.post(f"/clubs/{slug}/uploads?only={only}", files={"file": (name, io.BytesIO(data), ctype)})


def test_post_attachments_accept_real_documents_and_refuse_disguised_files():
    o = make_user("att_owner")
    mk(o, "att-club")
    img, pdf = up(o, "att-club", "banner.png", PNG), up(o, "att-club", "Agenda 2027.pdf", PDF)
    word, txt = up(o, "att-club", "minutes.docx", docx_bytes()), up(o, "att-club", "notes.txt", b"plain notes")
    assert [r.status_code for r in (img, pdf, word, txt)] == [201] * 4
    assert pdf.json()["kind"] == "document" and img.json()["kind"] == "image"
    # hostile or mislabeled files
    assert up(o, "att-club", "x.pdf", b"<html><script>alert(1)</script></html>").status_code == 415    # html renamed to pdf
    assert up(o, "att-club", "run.exe", b"MZ\x90\x00" + b"0" * 50).status_code == 415
    assert up(o, "att-club", "evil.docx", b"PK\x03\x04" + b"0" * 40).status_code == 415                  # not a real zip
    assert up(o, "att-club", "fake.docx", docx_bytes(root="xl/")).status_code == 415                       # real zip, wrong structure
    assert up(o, "att-club", "bad.txt", b"\xff\xfe\x00bin").status_code == 415
    assert up(o, "att-club", "doc.pdf", PDF, only="image").status_code == 415                              # default endpoint stays image-only
    ids = [x.json()["id"] for x in (img, pdf, word, txt)]
    post = o.post("/clubs/att-club/posts", json={"title": "Minutes", "body": "see files", "status": "published", "attachments": ids})
    assert post.status_code == 201 and [a["name"] for a in post.json()["attachments"]] == ["banner.png", "Agenda 2027.pdf", "minutes.docx", "notes.txt"]
    page = TestClient(app).get("/public/clubs/att-club").json()
    assert len(page["posts"][0]["attachments"]) == 4
    # downloads: documents are never rendered inside the site
    d = TestClient(app).get(pdf.json()["url"])
    assert d.status_code == 200 and d.content == PDF
    assert d.headers["content-disposition"].startswith("attachment") and "Agenda" in d.headers["content-disposition"]
    assert "sandbox" in d.headers["content-security-policy"] and d.headers["x-content-type-options"] == "nosniff"
    i = TestClient(app).get(img.json()["url"])
    assert "content-disposition" not in i.headers and i.headers["content-type"] == "image/png"
    # ownership + limits
    other = make_user("att_other")
    mk(other, "att-other")
    foreign = up(other, "att-other", "f.pdf", PDF).json()["id"]
    assert o.post("/clubs/att-club/posts", json={"title": "Steal", "body": "x", "attachments": [foreign]}).status_code == 422
    assert o.post("/clubs/att-club/posts", json={"title": "Many", "body": "x", "attachments": ids * 3}).status_code == 422
    # deleting a file removes it from posts
    assert o.delete(f"/clubs/att-club/uploads/{pdf.json()['id']}").status_code == 200
    assert len(TestClient(app).get("/public/clubs/att-club").json()["posts"][0]["attachments"]) == 3
    assert TestClient(app).get(pdf.json()["url"]).status_code == 404


def test_who_may_upload_attachments():
    o, writer, plain = make_user("wu_owner"), make_user("wu_writer"), make_user("wu_plain")
    mk(o, "upload-club")
    for u in (writer, plain):
        u.post("/clubs/upload-club/join", json={})
    mid = {m["user"]["username"]: m["id"] for m in o.get("/clubs/upload-club/members").json()}
    roles = {r["name"]: r["id"] for r in o.get("/clubs/upload-club/roles").json()}
    o.post("/clubs/upload-club/roles", json={"name": "Writer", "permissions": ["posts.manage"], "rank": 30})
    rid = next(r["id"] for r in o.get("/clubs/upload-club/roles").json() if r["name"] == "Writer")
    assert o.patch(f"/clubs/upload-club/members/{mid["wu_writer"]}", json={"role_id": rid}).status_code == 200
    assert up(writer, "upload-club", "a.pdf", PDF).status_code == 201          # posts.manage is enough to attach files
    assert up(plain, "upload-club", "a.pdf", PDF).status_code == 403
    assert up(make_user("wu_out"), "upload-club", "a.pdf", PDF).status_code == 404


# ------------------------------------------------------------------ approval
def test_club_creation_needs_super_admin_approval_and_is_spam_resistant():
    settings.club_approval_required = True
    try:
        o, other, admin, out = make_user("ap_owner"), make_user("ap_other"), make_user("ap_admin"), make_user("ap_out")
        make_admin(admin, "ap_admin")
        body = {"name": "Approval Club", "slug": "approval-club", "description": "We build robots and teach beginners every week."}
        assert o.post("/clubs", json={**body, "description": "too short"}).status_code == 422
        c = o.post("/clubs", json=body)
        assert c.status_code == 201 and c.json()["status"] == "pending"
        # invisible to everyone except its own members and platform admins
        anon = TestClient(app)
        assert anon.get("/clubs/approval-club").status_code == 404 and anon.get("/public/clubs/approval-club").status_code == 404
        assert out.post("/clubs/approval-club/join", json={}).status_code == 404
        assert "approval-club" not in [x["slug"] for x in anon.get("/discover/clubs?limit=50").json()]
        assert anon.get("/search?q=approval").json()["clubs"] == []
        assert o.get("/clubs/approval-club").status_code == 200 and admin.get("/clubs/approval-club").status_code == 200
        ev = o.post("/clubs/approval-club/events", json={"title": "Secret Event", "starts_at": NOW(48), "status": "published"}).json()
        assert anon.get(f"/events/{ev['slug']}").status_code == 404
        assert "Secret Event" not in [e["title"] for e in anon.get("/discover/events?limit=50").json()]
        # spam vectors are closed until approved
        assert o.post("/clubs/approval-club/invites", json={"username": "ap_out"}).json()["detail"]["code"] == "club_not_approved"
        assert o.post("/clubs/approval-club/communications", json={"subject": "x", "body": "y", "audience": {"type": "all_members"}}).status_code == 403
        # limits
        assert other.post("/clubs", json={**body, "slug": "dupe-name"}).status_code == 409                # same name as a live request
        assert o.post("/clubs", json={**body, "name": "Second Club", "slug": "second-club"}).status_code == 201
        assert o.post("/clubs", json={**body, "name": "Third Club", "slug": "third-club"}).status_code == 409   # max 2 pending
        # only super admins decide
        assert o.post("/admin/clubs/approval-club/approve").status_code == 403
        q = admin.get("/admin/clubs?status=pending").json()
        row = next(x for x in q if x["slug"] == "approval-club")
        assert row["owner"]["email"] == "ap_owner@ndc.edu.bd" and "account_age_days" in row["owner"] and row["description"].startswith("We build")
        assert any("awaiting approval" in n["title"] for n in admin.get("/notifications").json())
        assert admin.post("/admin/clubs/approval-club/approve").status_code == 200
        assert anon.get("/clubs/approval-club").status_code == 200
        assert "approval-club" in [x["slug"] for x in anon.get("/discover/clubs?limit=50").json()]
        assert any("approved" in n["title"] for n in o.get("/notifications").json())
        assert anon.get(f"/events/{ev['slug']}").status_code == 200
        # rejection with a reason, then fix and resubmit
        assert admin.post("/admin/clubs/second-club/reject", json={"reason": "x"}).status_code == 422
        assert admin.post("/admin/clubs/second-club/reject", json={"reason": "Looks like a duplicate of another club"}).status_code == 200
        mine = o.get("/clubs/second-club").json()
        assert mine["status"] == "rejected" and "duplicate" in mine["status_note"]
        assert anon.get("/clubs/second-club").status_code == 404
        assert o.post("/clubs/second-club/resubmit").json()["status"] == "pending"
        assert o.post("/clubs/approval-club/resubmit").status_code == 409                                    # only rejected clubs resubmit
        # platform admins skip the queue
        assert admin.post("/clubs", json={"name": "Admin Club", "slug": "admin-club"}).json()["status"] == "approved"
    finally:
        settings.club_approval_required = False


# ------------------------------------------------------------------ leaderboard
def test_leaderboard_is_optional_private_and_fair():
    o, m1, m2, m3, out = (make_user(n) for n in ("lb_owner", "lb_m1", "lb_m2", "lb_m3", "lb_out"))
    mk(o, "lb-club")
    for u in (m1, m2, m3):
        u.post("/clubs/lb-club/join", json={})
    assert m1.get("/clubs/lb-club/leaderboard").json()["detail"]["code"] == "leaderboard_off"             # off by default
    assert o.post("/clubs/lb-club/leaderboard/awards", json={"username": "lb_m1", "points": 5, "reason": "early"}).status_code == 404
    assert m1.patch("/clubs/lb-club", json={"leaderboard_enabled": True}).status_code == 403             # only club settings managers
    assert o.patch("/clubs/lb-club", json={"leaderboard_enabled": True}).json()["leaderboard_enabled"] is True
    aw = lambda c, who, pts, why="Helped run the workshop": c.post("/clubs/lb-club/leaderboard/awards", json={"username": who, "points": pts, "reason": why})  # noqa: E731
    assert aw(o, "lb_m1", 30).status_code == 201 and aw(o, "lb_m2", 30).status_code == 201 and aw(o, "lb_m3", 10).status_code == 201
    assert aw(o, "lb_owner", 10).status_code == 403                                                       # no self-awards, even for Owners
    assert aw(m1, "lb_m2", 5).status_code == 403                                                          # members can't award
    assert aw(o, "lb_out", 5).status_code == 404 and aw(o, "lb_m1", 0).status_code == 422 and aw(o, "lb_m1", 501).status_code == 422
    assert o.post("/clubs/lb-club/leaderboard/awards", json={"username": "lb_m1", "points": 5, "reason": "x"}).status_code == 422   # reason required
    board = m1.get("/clubs/lb-club/leaderboard").json()
    assert [(e["user"]["username"], e["points"], e["rank"]) for e in board["entries"]] == [("lb_m1", 30, 1), ("lb_m2", 30, 1), ("lb_m3", 10, 3)]   # ties share a rank
    assert board["me"]["rank"] == 1 and board["can_award"] is False
    assert any("+30 points" in n["title"] for n in m1.get("/notifications").json())
    # an admin (Executive) can award other admins and members; deductions need a reason too
    mid = {m["user"]["username"]: m["id"] for m in o.get("/clubs/lb-club/members").json()}
    roles = {r["name"]: r["id"] for r in o.get("/clubs/lb-club/roles").json()}
    assert o.patch(f"/clubs/lb-club/members/{mid['lb_m3']}", json={"role_id": roles["Executive"]}).status_code == 200
    assert m3.get("/clubs/lb-club/leaderboard").json()["can_award"] is True
    assert aw(m3, "lb_m1", -5, "No-show at the setup").status_code == 201
    assert aw(m3, "lb_owner", 20, "Ran the whole carnival").status_code == 201                            # admins can reward other admins
    # it never leaves the club
    assert out.get("/clubs/lb-club/leaderboard").status_code == 404
    assert TestClient(app).get("/clubs/lb-club/leaderboard").status_code == 401
    assert "leaderboard" not in str(TestClient(app).get("/public/clubs/lb-club").json()["posts"])
    # history: own entries only, unless you manage points
    assert [h["points"] for h in m1.get("/clubs/lb-club/leaderboard/history").json()] == [-5, 30]
    assert m1.get("/clubs/lb-club/leaderboard/history?username=lb_m2").status_code == 403
    assert len(o.get("/clubs/lb-club/leaderboard/history?username=lb_m2").json()) == 1
    assert m1.get("/clubs/lb-club/leaderboard/recent").status_code == 403 and len(o.get("/clubs/lb-club/leaderboard/recent").json()) == 5
    # monthly board excludes old entries; revoking removes points
    with SessionLocal() as db:
        e = db.scalars(select(PointEntry).where(PointEntry.points == 10)).first()
        e.created_at = datetime.now(timezone.utc) - timedelta(days=70)
        db.commit()
    assert "lb_m3" not in [x["user"]["username"] for x in m1.get("/clubs/lb-club/leaderboard?period=month").json()["entries"]]
    assert "lb_m3" in [x["user"]["username"] for x in m1.get("/clubs/lb-club/leaderboard?period=all").json()["entries"]]
    rid = next(x["id"] for x in o.get("/clubs/lb-club/leaderboard/recent").json() if x["points"] == -5)
    assert o.delete(f"/clubs/lb-club/leaderboard/awards/{rid}").status_code == 200
    assert next(e for e in m1.get("/clubs/lb-club/leaderboard").json()["entries"] if e["user"]["username"] == "lb_m1")["points"] == 30
    assert any(a["action"] == "points.awarded" for a in o.get("/clubs/lb-club/audit").json()) and any(a["action"] == "points.revoked" for a in o.get("/clubs/lb-club/audit").json())
    # a club can switch it off again (data is kept, just hidden)
    o.patch("/clubs/lb-club", json={"leaderboard_enabled": False})
    assert m1.get("/clubs/lb-club/leaderboard").status_code == 404


def test_new_permissions_reach_existing_clubs_on_startup():
    o = make_user("sync_owner")
    mk(o, "sync-club")
    with SessionLocal() as db:
        r = db.scalars(select(Role).where(Role.name == "Executive", Role.club_id == db.scalars(select(Role.club_id).where(Role.name == "Executive").limit(1)).first())).first()
        r.permissions = [p for p in r.permissions if p != "points.manage"]
        db.commit()
        assert sync_system_roles(db) >= 1
        db.commit()
        db.refresh(r)
        assert "points.manage" in r.permissions


# ------------------------------------------------------------------ admin self-check
def test_system_check_flags_the_images_vanish_on_render_mistake():
    admin, o = make_user("sys_admin"), make_user("sys_owner")
    make_admin(admin, "sys_admin")
    mk(o, "sys-club")
    r = up(o, "sys-club", "logo.png", PNG, only="image")
    assert r.status_code == 201
    os.remove(os.path.join(settings.media_dir, r.json()["url"].split("/")[2], r.json()["url"].split("/")[3]))   # the ephemeral disk lost it
    os.environ["RENDER"] = "true"
    try:
        s = admin.get("/admin/system").json()
    finally:
        del os.environ["RENDER"]
    assert s["uploads_missing"] >= 1 and s["media_backend"] == "disk"
    text = " ".join(s["warnings"])
    assert "MEDIA_BACKEND" in text and "missing from storage" in text
    assert o.get("/admin/system").status_code == 403
