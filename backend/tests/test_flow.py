from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import EmailOutbox, User
from app.services.mail import process_outbox
from tests.conftest import PASSWORD, db_set_plan, last_mail, make_user, verify

FUTURE = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
FUTURE_END = (datetime.now(timezone.utc) + timedelta(days=10, hours=3)).isoformat()


class FakeSender:
    def __init__(self, fail_for=()):
        self.sent, self.fail_for = [], set(fail_for)

    def send(self, to, subject, body, unsubscribe_url=None):
        if to in self.fail_for:
            raise RuntimeError("smtp down")
        self.sent.append((to, subject, body))
        self.unsub = getattr(self, "unsub", []) + [unsubscribe_url]


def test_auth_lifecycle():
    c = make_user("alice", verified=False)
    assert c.post("/clubs", json={"name": "X Club", "slug": "x-club"}).status_code == 403  # unverified
    verify(c, "alice@ndc.edu.bd")
    assert c.get("/users/me").json()["email_verified"] is True
    # wrong password x5 -> lockout, even with the right password afterwards
    bad = make_user("mallory")
    for _ in range(5):
        assert bad.post("/auth/login", json={"email": "mallory@ndc.edu.bd", "password": "wrong-password-1"}).status_code == 401
    assert bad.post("/auth/login", json={"email": "mallory@ndc.edu.bd", "password": PASSWORD}).status_code == 429
    # password reset revokes sessions
    c.post("/auth/password-reset/request", json={"email": "alice@ndc.edu.bd"})
    import re
    tok = re.search(r"token=([\w-]+)", last_mail("alice@ndc.edu.bd")).group(1)
    assert c.post("/auth/password-reset/confirm", json={"token": tok, "password": "a-brand-new-password"}).status_code == 200
    assert c.get("/users/me").status_code == 401
    assert c.post("/auth/password-reset/confirm", json={"token": tok, "password": "another-new-password"}).status_code == 400  # single use
    assert c.post("/auth/login", json={"email": "alice@ndc.edu.bd", "password": "a-brand-new-password"}).status_code == 200


def test_full_club_event_flow():
    owner, admin, vol, s1, s2, s3, outsider = (make_user(n) for n in ["owner", "adm", "vol", "stu1", "stu2", "stu3", "outsider"])

    # ---- club creation + visibility --------------------------------------------------------
    r = owner.post("/clubs", json={"name": "NDC Robotics", "slug": "ndc-robotics", "category": "technology", "join_policy": "request"})
    assert r.status_code == 201, r.text
    db_set_plan("ndc-robotics", "pro")  # this flow exercises Pro features; free limits are covered in test_plans
    assert owner.post("/clubs", json={"name": "Dup", "slug": "ndc-robotics"}).status_code == 409
    assert owner.post("/clubs", json={"name": "Bad", "slug": "admin"}).status_code == 422
    secret = owner.post("/clubs", json={"name": "Secret Society", "slug": "secret-soc", "visibility": "private", "join_policy": "invite"})
    assert secret.status_code == 201
    assert outsider.get("/clubs/secret-soc").status_code == 404                      # private clubs don't leak
    assert outsider.get("/public/clubs/secret-soc").status_code == 404
    assert "secret-soc" not in [c["slug"] for c in outsider.get("/discover/clubs").json()]
    assert outsider.post("/clubs/secret-soc/join", json={}).status_code == 404

    # ---- theme is constrained --------------------------------------------------------------
    assert owner.patch("/clubs/ndc-robotics", json={"theme": {"preset": "neon-vomit"}}).status_code == 422
    assert owner.patch("/clubs/ndc-robotics", json={"theme": {"preset": "editorial", "primary": "#112233"}}).status_code == 200

    # ---- application form + join request + approval ----------------------------------------
    fields = [{"id": "motivation", "type": "textarea", "label": "Why join?", "required": True}]
    assert owner.patch("/clubs/ndc-robotics", json={"application_fields": fields}).status_code == 200
    assert vol.post("/clubs/ndc-robotics/join", json={"application": {}}).status_code == 422  # missing required
    for u in (vol, admin, s1, s2, s3):
        assert u.post("/clubs/ndc-robotics/join", json={"application": {"motivation": "I love robots"}}).status_code == 200
    assert s1.post("/clubs/ndc-robotics/join", json={}).status_code == 409
    members = owner.get("/clubs/ndc-robotics/members?status=pending").json()
    assert len(members) == 5 and members[0]["application"]["motivation"] == "I love robots"
    ids = {m["user"]["username"]: m["id"] for m in members}
    for name in ("vol", "adm", "stu1", "stu2", "stu3"):
        assert owner.patch(f"/clubs/ndc-robotics/members/{ids[name]}", json={"status": "active"}).status_code == 200
    assert any("approved" in n["title"] for n in s1.get("/notifications").json())

    # ---- roles: escalation guards ----------------------------------------------------------
    roles = {r["name"]: r["id"] for r in owner.get("/clubs/ndc-robotics/roles").json()}
    assert owner.patch(f"/clubs/ndc-robotics/members/{ids['adm']}", json={"role_id": roles["Administrator"]}).status_code == 200
    assert owner.patch(f"/clubs/ndc-robotics/members/{ids['vol']}", json={"role_id": roles["Volunteer"]}).status_code == 200
    # admin cannot promote anyone to Owner, nor create a role above own rank, nor modify the owner
    assert admin.patch(f"/clubs/ndc-robotics/members/{ids['stu1']}", json={"role_id": roles["Owner"]}).status_code == 403
    assert admin.post("/clubs/ndc-robotics/roles", json={"name": "Super", "permissions": ["audit.view"], "rank": 95}).status_code == 422
    owner_member_id = next(m["id"] for m in owner.get("/clubs/ndc-robotics/members").json() if m["user"]["username"] == "owner")
    assert admin.patch(f"/clubs/ndc-robotics/members/{owner_member_id}", json={"status": "suspended"}).status_code == 403
    # volunteer has no member permissions at all
    assert vol.get("/clubs/ndc-robotics/members").status_code == 403
    assert outsider.get("/clubs/ndc-robotics/members").status_code == 404
    # custom role + cannot grant perms you don't hold
    assert owner.post("/clubs/ndc-robotics/roles", json={"name": "Media Secretary", "permissions": ["posts.manage", "events.manage"], "rank": 40}).status_code == 201
    # last owner protection
    assert owner.post("/clubs/ndc-robotics/leave").status_code == 400

    # ---- posts: drafts hidden, scheduled hidden, published visible -------------------------
    assert owner.post("/clubs/ndc-robotics/posts", json={"title": "Draft", "body": "hidden"}).status_code == 201
    assert owner.post("/clubs/ndc-robotics/posts", json={"title": "Later", "body": "x", "status": "published", "publish_at": FUTURE}).status_code == 201
    assert owner.post("/clubs/ndc-robotics/posts", json={"title": "Hello", "body": "world", "status": "published", "pinned": True}).status_code == 201
    assert [p["title"] for p in outsider.get("/clubs/ndc-robotics/posts").json()] == ["Hello"]
    assert len(owner.get("/clubs/ndc-robotics/posts?drafts=true").json()) == 3
    assert vol.post("/clubs/ndc-robotics/posts", json={"title": "nope", "body": "x"}).status_code == 403

    # ---- event with conditional registration form, capacity 2 ------------------------------
    reg_fields = [
        {"id": "workshop", "type": "radio", "label": "Attend workshop?", "options": ["yes", "no"], "required": True},
        {"id": "laptop", "type": "dropdown", "label": "Laptop OS", "options": ["linux", "windows", "mac"], "required": True,
         "show_if": {"field": "workshop", "equals": "yes"}},
        {"id": "notes", "type": "text", "label": "Notes"},
    ]
    r = owner.post("/clubs/ndc-robotics/events", json={"title": "Tech Carnival 2027", "description": "Fun", "venue": "Hall 1",
                   "starts_at": FUTURE, "ends_at": FUTURE_END, "capacity": 2, "status": "published", "registration_fields": reg_fields})
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]
    past_end = (datetime.now(timezone.utc) + timedelta(days=9)).isoformat()
    assert owner.post("/clubs/ndc-robotics/events", json={"title": "Bad dates", "starts_at": FUTURE, "ends_at": past_end}).status_code == 422
    assert outsider.get(f"/events/{slug}").status_code == 200  # public
    assert any(e["slug"] == slug for e in outsider.get("/discover/events").json())
    assert any(e["slug"] == slug for e in outsider.get("/search?q=carnival").json()["events"])

    assert s1.post(f"/events/{slug}/register", json={"answers": {}}).status_code == 422
    assert s1.post(f"/events/{slug}/register", json={"answers": {"workshop": "yes"}}).status_code == 422  # conditional required
    r1 = s1.post(f"/events/{slug}/register", json={"answers": {"workshop": "yes", "laptop": "linux", "notes": "=cmd|' /C calc'!A0"}})
    assert r1.status_code == 201 and r1.json()["status"] == "confirmed"
    assert s1.post(f"/events/{slug}/register", json={"answers": {"workshop": "no"}}).status_code == 409  # duplicate
    r2 = s2.post(f"/events/{slug}/register", json={"answers": {"workshop": "no", "laptop": "mac"}})  # hidden field ignored
    assert r2.json()["status"] == "confirmed"
    r3 = s3.post(f"/events/{slug}/register", json={"answers": {"workshop": "no"}})
    assert r3.json()["status"] == "waitlisted"
    assert "Registration ID" in last_mail("stu1@ndc.edu.bd")

    # cancel -> waitlist promotion
    assert s1.delete(f"/events/{slug}/register").status_code == 200
    assert s3.get(f"/events/{slug}").json()["my_registration"]["status"] == "confirmed"
    assert any("You're in" in n["title"] for n in s3.get("/notifications").json())

    # ---- QR + check-in ---------------------------------------------------------------------
    t3 = s3.get(f"/events/{slug}").json()["my_registration"]
    qr = s3.get(f"/registrations/{t3['id']}/qr.svg")
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/svg+xml" and b"<svg" in qr.content
    assert s2.get(f"/registrations/{t3['id']}/qr.svg").status_code == 404  # other people's tickets are private
    assert s3.post(f"/events/{slug}/checkin", json={"ticket_code": t3["ticket_code"]}).status_code == 403  # attendee can't scan
    assert outsider.post(f"/events/{slug}/checkin", json={"ticket_code": t3["ticket_code"]}).status_code == 404
    ok = vol.post(f"/events/{slug}/checkin", json={"ticket_code": t3["ticket_code"].lower()})
    assert ok.status_code == 200, ok.text
    dup = vol.post(f"/events/{slug}/checkin", json={"ticket_code": t3["ticket_code"]})
    assert dup.status_code == 409
    assert vol.post(f"/events/{slug}/checkin", json={"ticket_code": r1.json()["ticket_code"]}).status_code == 404  # cancelled ticket
    att = vol.get(f"/events/{slug}/attendance").json()
    assert att["confirmed"] == 2 and att["checked_in"] == 1 and att["attendance_rate"] == 0.5

    # cross-club isolation: a second club can't scan this club's tickets or read its registrations
    other = make_user("otherowner")
    assert other.post("/clubs", json={"name": "Other Club", "slug": "other-club"}).status_code == 201
    assert other.post(f"/events/{slug}/checkin", json={"ticket_code": t3["ticket_code"]}).status_code == 404
    assert other.get(f"/events/{slug}/registrations").status_code == 404
    e2 = other.post("/clubs/other-club/events", json={"title": "Other Event", "starts_at": FUTURE, "status": "published"}).json()["slug"]
    assert other.post(f"/events/{e2}/checkin", json={"ticket_code": t3["ticket_code"]}).status_code == 404  # ticket scoped to its event

    # ---- registrations export is formula-injection safe ------------------------------------
    assert vol.get(f"/events/{slug}/registrations").status_code == 403
    csv_text = owner.get(f"/events/{slug}/registrations.csv").text
    assert "'=cmd" in csv_text and ",=cmd" not in csv_text

    # ---- bulk email: personalization, audiences, validation, worker ------------------------
    assert vol.post("/clubs/ndc-robotics/communications", json={"subject": "hi", "body": "x", "audience": {"type": "all_members"}}).status_code == 403
    assert owner.post("/clubs/ndc-robotics/communications", json={"subject": "hi {{secret}}", "body": "x", "audience": {"type": "all_members"}}).status_code == 422
    assert owner.post("/clubs/ndc-robotics/communications", json={"subject": "x", "body": "x", "audience": {"type": "event_registered", "event_slug": e2}}).status_code == 404
    r = owner.post("/clubs/ndc-robotics/communications", json={
        "subject": "Reminder: {{event_name}}", "body": "Hi {{first_name}}, see you at {{event_name}}! — {{club_name}}",
        "audience": {"type": "event_not_checked_in", "event_slug": slug}})
    assert r.status_code == 201 and r.json()["queued"] == 1   # only stu2: stu3 checked in, stu1 cancelled
    with SessionLocal() as db:
        fs = FakeSender(fail_for={"stu2@ndc.edu.bd"})
        sent, failed = process_outbox(db, fs, batch=500)
        assert failed == 0  # first failure is retried, not abandoned
        row = db.scalars(select(EmailOutbox).where(EmailOutbox.to_email == "stu2@ndc.edu.bd", EmailOutbox.subject.like("Reminder%"))).one()
        assert row.status == "pending" and row.attempts == 1 and row.send_at is not None
        row.send_at = None
        db.commit()
        fs.fail_for.clear()
        process_outbox(db, fs, batch=500)
        db.refresh(row)
        assert row.status == "sent"
        assert any(s[0] == "stu2@ndc.edu.bd" and s[2].startswith("Hi Stu2,") and "Tech Carnival 2027" in s[1] for s in fs.sent)

    # ---- cancelling an event notifies registrants ------------------------------------------
    assert owner.patch(f"/events/{slug}", json={"status": "cancelled"}).status_code == 200
    assert any("cancelled" in n["title"].lower() for n in s2.get("/notifications").json())

    # ---- standalone forms ------------------------------------------------------------------
    f = owner.post("/clubs/ndc-robotics/forms", json={"title": "Feedback", "fields": [{"id": "rating", "type": "number", "label": "Rating", "required": True}], "max_submissions": 1}).json()
    assert s1.post(f"/forms/{f['id']}/submit", json={"rating": 5}).status_code == 201
    assert s1.post(f"/forms/{f['id']}/submit", json={"rating": 5}).status_code == 409
    assert s2.post(f"/forms/{f['id']}/submit", json={"rating": 4}).status_code == 409  # full
    assert outsider.post(f"/forms/{f['id']}/submit", json={"rating": 1}).status_code == 404
    assert len(owner.get(f"/clubs/ndc-robotics/forms/{f['id']}/submissions").json()) == 1

    # ---- dashboard + audit -----------------------------------------------------------------
    d = owner.get("/clubs/ndc-robotics/dashboard").json()
    assert d["stats"]["active_members"] == 6 and "create_event" in d["actions"]
    assert "attention" in vol.get("/clubs/ndc-robotics/dashboard").json()
    actions = [a["action"] for a in owner.get("/clubs/ndc-robotics/audit").json()]
    assert "member.updated" in actions and "event.created" in actions and "communication.sent" in actions
    assert vol.get("/clubs/ndc-robotics/audit").status_code == 403

    # ---- plan limits + platform admin ------------------------------------------------------
    assert owner.post("/admin/clubs/ndc-robotics/plan", json={"plan": "pro"}).status_code == 403
    from tests.conftest import make_admin
    make_admin(owner, "owner")
    assert owner.post("/admin/clubs/ndc-robotics/plan", json={"plan": "pro", "months": 2}).status_code == 200
    assert owner.post("/admin/clubs/ndc-robotics/verify").status_code == 200
    assert owner.get("/clubs/ndc-robotics").json()["verified"] is True
    assert owner.get("/admin/stats").json()["clubs"] >= 3


def test_institution_visibility_uses_verified_email_domain():
    a = make_user("instadmin")
    assert a.post("/institutions", json={"name": "Notre Dame College", "slug": "ndc", "email_domain": "ndc.edu.bd"}).status_code == 201
    assert a.post("/clubs", json={"name": "NDC Only", "slug": "ndc-only", "visibility": "institution", "institution_slug": "ndc"}).status_code == 201
    member = make_user("insider")                      # ...@ndc.edu.bd, verified
    assert member.get("/clubs/ndc-only").status_code == 200
    from fastapi.testclient import TestClient
    from app.main import app
    ext = TestClient(app)
    ext.post("/auth/register", json={"email": "ext@gmail.com", "username": "ext", "password": PASSWORD, "full_name": "Ext User", "accept_terms": True})
    verify(ext, "ext@gmail.com")
    ext.post("/auth/login", json={"email": "ext@gmail.com", "password": PASSWORD})
    assert ext.get("/clubs/ndc-only").status_code == 404
    assert "ndc-only" not in [c["slug"] for c in ext.get("/discover/clubs").json()]   # institution-only never in global discovery
    assert TestClient(app).get("/clubs/ndc-only").status_code == 404                  # anonymous


def test_profile_privacy():
    u = make_user("privacy")
    assert make_user("viewer0").get("/users/privacy").status_code == 404           # private by default
    u.patch("/users/me", json={"profile_public": True})
    assert "email" not in make_user("viewer").get("/users/privacy").json()
    u.patch("/users/me", json={"show_email": True, "bio": "hi"})
    assert make_user("viewer2").get("/users/privacy").json()["email"] == "privacy@ndc.edu.bd"
    u.patch("/users/me", json={"profile_public": False})
    assert make_user("viewer3").get("/users/privacy").status_code == 404
    assert u.get("/users/privacy").status_code == 200
