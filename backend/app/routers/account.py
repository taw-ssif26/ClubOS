"""Account safety and privacy: password change, verification resend, 2FA, data export, deletion, email unsubscribe."""
import io
import secrets
from datetime import timedelta
from uuid import UUID

import pyotp
import segno
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import (Club, EmailOptOut, EmailOutbox, EmailToken, LoginEvent, Membership, Notification, Registration, Review,
                      Session as UserSession, Submission, User, aware, utcnow)
from ..net import client_ip
from ..ratelimit import rate_limit
from ..security import hash_password, new_token, token_hash, verify_password
from ..services.core import audit, iso
from ..services.crypto import check_sig, decrypt, encrypt, verify_totp
from ..services.mail import queue_email

router = APIRouter(tags=["account"])


# ---- password + verification ---------------------------------------------------------------

class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


@router.post("/auth/change-password", dependencies=[Depends(rate_limit("chpw", 10, 3600))])
def change_password(body: ChangePasswordIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(403, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked.is_(False), UserSession.id != request.state.session_id)):
        s.revoked = True  # every other device is signed out
    db.commit()
    return {"ok": True}


@router.post("/auth/resend-verification", dependencies=[Depends(rate_limit("resend", 6, 3600))])
def resend_verification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.email_verified:
        return {"ok": True}
    last = db.scalar(select(EmailToken.created_at).where(EmailToken.user_id == user.id, EmailToken.kind == "verify").order_by(EmailToken.created_at.desc()).limit(1))
    if last and aware(last) > utcnow() - timedelta(seconds=60):
        raise HTTPException(429, "A verification email was just sent. Check your inbox and spam folder, or wait a minute.")
    raw = new_token()
    db.add(EmailToken(user_id=user.id, kind="verify", token_hash=token_hash(raw), expires_at=utcnow() + timedelta(hours=48)))
    queue_email(db, to=user.email, subject="Verify your ClubOS email",
                body=f"Hi {user.full_name.split()[0]},\n\nConfirm your email:\n{settings.base_url}/verify-email?token={raw}\n")
    db.commit()
    return {"ok": True}


# ---- two-factor ----------------------------------------------------------------------------

class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class DisableIn(CodeIn):
    password: str = Field(max_length=128)


@router.post("/auth/2fa/setup", dependencies=[Depends(rate_limit("2fa", 10, 3600))])
def totp_setup(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.totp_enabled:
        raise HTTPException(409, "Two-factor authentication is already enabled")
    secret = pyotp.random_base32()
    user.totp_secret = encrypt(secret)
    db.commit()
    return {"secret": secret, "uri": pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="ClubOS")}


@router.get("/auth/2fa/qr.svg")
def totp_qr(user: User = Depends(current_user)):
    if not user.totp_secret or user.totp_enabled:
        raise HTTPException(404, "No setup in progress")
    uri = pyotp.TOTP(decrypt(user.totp_secret)).provisioning_uri(name=user.email, issuer_name="ClubOS")
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=6, border=2, dark="#000", light="#fff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


@router.post("/auth/2fa/enable", dependencies=[Depends(rate_limit("2fa", 10, 3600))])
def totp_enable(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.totp_secret or user.totp_enabled:
        raise HTTPException(409, "Start setup first")
    if not verify_totp(user, body.code):
        raise HTTPException(422, "That code is not valid. Check your authenticator app's clock and try again.")
    user.totp_enabled = True
    audit(db, None, user.id, "2fa.enabled", user.username)
    db.commit()
    return {"ok": True}


@router.post("/auth/2fa/disable", dependencies=[Depends(rate_limit("2fa", 10, 3600))])
def totp_disable(body: DisableIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.totp_enabled:
        raise HTTPException(409, "Two-factor authentication is not enabled")
    if not verify_password(user.password_hash, body.password) or not verify_totp(user, body.code):
        raise HTTPException(403, "Password or code is incorrect")
    user.totp_enabled, user.totp_secret = False, None
    audit(db, None, user.id, "2fa.disabled", user.username)
    db.commit()
    return {"ok": True}


# ---- data export + deletion ----------------------------------------------------------------

@router.get("/users/me/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything ClubOS holds about the signed-in person, as JSON."""
    mem = db.scalars(select(Membership).where(Membership.user_id == user.id)).unique().all()
    regs = db.scalars(select(Registration).where(Registration.user_id == user.id)).unique().all()
    revs = db.scalars(select(Review).where(Review.user_id == user.id)).unique().all()
    subs = db.scalars(select(Submission).where(Submission.user_id == user.id)).unique().all()
    logins = db.scalars(select(LoginEvent).where(LoginEvent.user_id == user.id).order_by(LoginEvent.created_at.desc()).limit(200)).all()
    body = {
        "exported_at": iso(utcnow()),
        "profile": {"email": user.email, "username": user.username, "full_name": user.full_name, "bio": user.bio, "institution": user.institution,
                    "department": user.department, "class_year": user.class_year, "skills": user.skills, "social_links": user.social_links,
                    "profile_public": user.profile_public, "created_at": iso(user.created_at), "terms_accepted_at": iso(user.terms_accepted_at), "terms_version": user.terms_version},
        "memberships": [{"club": m.club.name, "role": m.role.name, "status": m.status, "application": m.application, "joined_at": iso(m.joined_at)} for m in mem],
        "registrations": [{"event": r.event.title, "status": r.status, "answers": r.answers, "ticket_code": r.ticket_code, "checked_in_at": iso(r.checked_in_at)} for r in regs],
        "reviews": [{"target": r.target_type, "club": r.club.name, "rating": r.rating, "title": r.title, "body": r.body, "created_at": iso(r.created_at)} for r in revs],
        "form_submissions": [{"data": s.data, "at": iso(s.created_at)} for s in subs],
        "sign_in_history": [{"ip": l.ip, "user_agent": l.user_agent, "success": l.success, "at": iso(l.created_at)} for l in logins],
    }
    return Response(__import__("json").dumps(body, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="clubos-my-data.json"', "Cache-Control": "no-store"})


class DeleteIn(BaseModel):
    password: str = Field(max_length=128)
    code: str | None = None


@router.delete("/users/me", dependencies=[Depends(rate_limit("delete-account", 5, 3600))])
def delete_account(body: DeleteIn, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Anonymizes the account. Events keep aggregate attendance; the person's identity, reviews and sessions are removed."""
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(403, "Password is incorrect")
    if user.totp_enabled and not verify_totp(user, body.code or ""):
        raise HTTPException(403, "Authentication code is incorrect")
    blocking = []
    for m in db.scalars(select(Membership).where(Membership.user_id == user.id, Membership.status == "active")).unique():
        if "*" in (m.role.permissions or []):
            others = [o for o in db.scalars(select(Membership).where(Membership.club_id == m.club_id, Membership.status == "active", Membership.user_id != user.id)).unique()
                      if "*" in (o.role.permissions or [])]
            if not others:
                blocking.append(m.club.name)
    if blocking:
        raise HTTPException(409, f"You are the only Owner of: {', '.join(blocking)}. Promote another member to Owner first.")
    tag = secrets.token_hex(4)
    for m in db.scalars(select(Membership).where(Membership.user_id == user.id)).unique():
        m.status, m.application, m.notes = "former", {}, ""
    for r in db.scalars(select(Registration).where(Registration.user_id == user.id, Registration.status != "cancelled")).unique():
        if r.checked_in_at is None:
            r.status = "cancelled"
        r.answers = {}
    for s in db.scalars(select(Submission).where(Submission.user_id == user.id)):
        s.data = {}
    old_email = user.email
    db.execute(delete(Review).where(Review.user_id == user.id))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(LoginEvent).where(LoginEvent.user_id == user.id))
    db.execute(delete(EmailOptOut).where(EmailOptOut.user_id == user.id))
    db.execute(delete(EmailOutbox).where(EmailOutbox.to_email == old_email, EmailOutbox.status == "pending"))
    user.email, user.username, user.full_name = f"deleted-{tag}@deleted.invalid", f"deleted_{tag}", "Deleted user"
    user.bio, user.avatar_url, user.institution, user.department, user.class_year = "", None, None, None, None
    user.skills, user.social_links, user.profile_public = [], {}, False
    user.password_hash, user.is_active, user.email_verified = hash_password(secrets.token_urlsafe(32)), False, False
    user.totp_secret, user.totp_enabled = None, False
    audit(db, None, None, "account.deleted", f"deleted_{tag}")
    db.commit()
    response.delete_cookie("clubos_session", path="/")
    return {"ok": True}


# ---- unsubscribe (club email) --------------------------------------------------------------

class UnsubIn(BaseModel):
    u: UUID
    c: UUID
    t: str = Field(max_length=64)


def unsubscribe_url(user_id, club_id) -> str:
    from ..services.crypto import sign
    return f"{settings.base_url}/unsubscribe?u={user_id}&c={club_id}&t={sign(str(user_id), str(club_id))}"


@router.post("/unsubscribe", dependencies=[Depends(rate_limit("unsub", 60, 3600, per="ip"))])
def unsubscribe(body: UnsubIn, db: Session = Depends(get_db)):
    if not check_sig(body.t, str(body.u), str(body.c)):
        raise HTTPException(400, "This unsubscribe link is not valid")
    club = db.get(Club, body.c)
    if not db.scalar(select(EmailOptOut.id).where(EmailOptOut.user_id == body.u, EmailOptOut.club_id == body.c)):
        db.add(EmailOptOut(user_id=body.u, club_id=body.c))
        db.commit()
    return {"ok": True, "club": club.name if club else None}
