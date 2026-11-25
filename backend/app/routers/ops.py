"""Club operations: plan usage, upgrade requests, analytics, calendar feed, data export, uploads."""
import csv
import io
import os
import re
import uuid
import zipfile
from collections import Counter
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import ClubCtx, can_view_club, club_perm, club_perm_any, current_user_optional, get_club_or_404, get_membership
from ..models import Event, Membership, Plan, Post, Registration, Upload, UpgradeRequest, User, aware, utcnow
from ..ratelimit import rate_limit
from ..services.core import audit, csv_safe, iso, notify
from ..services.plans import get_limits, require_flag, storage_used, usage

router = APIRouter(prefix="/clubs/{slug}", tags=["operations"])


@router.get("/usage")
def club_usage(ctx: ClubCtx = Depends(club_perm(None)), db: Session = Depends(get_db)):
    return usage(db, ctx.club)


# ---- manual billing ------------------------------------------------------------------------

class UpgradeIn(BaseModel):
    plan_key: str
    months: int = Field(1, ge=1, le=12)
    contact: str = Field(min_length=5, max_length=120)  # bKash/Nagad number or email we confirm payment with
    message: str = Field("", max_length=1000)


@router.post("/upgrade-requests", status_code=201, dependencies=[Depends(rate_limit("upgrade", 10, 3600))])
def request_upgrade(body: UpgradeIn, ctx: ClubCtx = Depends(club_perm("club.settings")), db: Session = Depends(get_db)):
    plan = db.scalar(select(Plan).where(Plan.key == body.plan_key, Plan.visible.is_(True)))
    if ctx.club.status != "approved":
        raise HTTPException(403, "Your club must be approved before you can request a paid plan")
    if not plan or plan.key == "free":
        raise HTTPException(422, "Choose a paid plan")
    if db.scalar(select(UpgradeRequest.id).where(UpgradeRequest.club_id == ctx.club.id, UpgradeRequest.status == "pending")):
        raise HTTPException(409, "You already have a pending request. We'll contact you shortly.")
    db.add(UpgradeRequest(club_id=ctx.club.id, user_id=ctx.user.id, plan_key=plan.key, months=body.months,
                          contact=body.contact, message=body.message))
    for a in db.scalars(select(User).where(User.is_platform_admin.is_(True))):
        notify(db, a.id, f"Upgrade request: {ctx.club.name} → {plan.name}", body.contact, "/admin")
    audit(db, ctx.club.id, ctx.user.id, "billing.upgrade_requested", plan.key)
    db.commit()
    return {"ok": True}


@router.get("/upgrade-requests")
def my_upgrade_requests(ctx: ClubCtx = Depends(club_perm("club.settings")), db: Session = Depends(get_db)):
    rows = db.scalars(select(UpgradeRequest).where(UpgradeRequest.club_id == ctx.club.id).order_by(UpgradeRequest.created_at.desc()).limit(10)).unique()
    return [{"id": str(r.id), "plan_key": r.plan_key, "months": r.months, "status": r.status, "created_at": iso(r.created_at)} for r in rows]


# ---- analytics -----------------------------------------------------------------------------

@router.get("/analytics")
def analytics(ctx: ClubCtx = Depends(club_perm("analytics.view")), db: Session = Depends(get_db)):
    club = ctx.club
    now = utcnow()
    members = db.scalar(select(func.count()).select_from(Membership).where(Membership.club_id == club.id, Membership.status == "active"))
    events_total = db.scalar(select(func.count()).select_from(Event).where(Event.club_id == club.id, Event.status != "draft"))
    regs_total = db.scalar(select(func.count()).select_from(Registration).join(Event, Event.id == Registration.event_id)
                           .where(Event.club_id == club.id, Registration.status == "confirmed"))
    out = {"basic": {"members": members, "events": events_total, "registrations": regs_total}, "advanced": None}
    if not get_limits(db, club).get("advanced_analytics"):
        out["upgrade_required"] = "advanced_analytics"
        return out
    joined = [aware(j) for j in db.scalars(select(Membership.joined_at).where(Membership.club_id == club.id, Membership.joined_at.is_not(None)))]
    by_month = Counter(j.strftime("%Y-%m") for j in joined)
    months, running = [], 0
    for key in sorted(by_month):
        running += by_month[key]
        months.append({"month": key, "joined": by_month[key], "total": running})
    former = db.scalar(select(func.count()).select_from(Membership).where(Membership.club_id == club.id, Membership.status == "former"))
    evs = db.scalars(select(Event).where(Event.club_id == club.id, Event.status == "published").order_by(Event.starts_at.desc()).limit(20)).unique().all()
    perf = []
    for e in evs:
        conf = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id, Registration.status == "confirmed"))
        att = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id, Registration.status == "confirmed", Registration.checked_in_at.is_not(None)))
        wl = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id, Registration.status == "waitlisted"))
        perf.append({"slug": e.slug, "title": e.title, "starts_at": iso(e.starts_at), "capacity": e.capacity, "registered": conf, "attended": att,
                     "waitlisted": wl, "attendance_rate": round(att / conf, 3) if conf else None,
                     "fill_rate": round(conf / e.capacity, 3) if e.capacity else None})
    out["advanced"] = {"member_growth": months, "retention": round(members / (members + former), 3) if (members + former) else None, "events": perf}
    return out


# ---- exports + calendar --------------------------------------------------------------------

@router.get("/members.csv")
def export_members(ctx: ClubCtx = Depends(club_perm("members.manage")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Membership).where(Membership.club_id == ctx.club.id).order_by(Membership.created_at)).unique().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "username", "email", "role", "status", "joined_at", "department", "class_year"])
    for m in rows:
        w.writerow([csv_safe(x) for x in [m.user.full_name, m.user.username, m.user.email, m.role.name, m.status, iso(m.joined_at), m.user.department, m.user.class_year]])
    audit(db, ctx.club.id, ctx.user.id, "members.exported", None, {"rows": len(rows)})
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{ctx.club.slug}-members.csv"'})


def _esc(t: str) -> str:
    return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode()) > 73:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def _ics_dt(dt) -> str:
    return aware(dt).strftime("%Y%m%dT%H%M%SZ")


@router.get("/calendar.ics")
def calendar_feed(slug: str, user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    m = get_membership(db, club.id, user.id if user else None)
    if not can_view_club(db, club, user, m):
        raise HTTPException(404, "Club not found")
    q = select(Event).where(Event.club_id == club.id, Event.status == "published", Event.visibility == "public",
                            Event.starts_at >= utcnow() - timedelta(days=30)).order_by(Event.starts_at)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ClubOS//Club calendar//EN", "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{_esc(club.name)}"]
    for e in db.scalars(q).unique():
        end = e.ends_at or (aware(e.starts_at) + timedelta(hours=2))
        lines += ["BEGIN:VEVENT", f"UID:{e.id}@clubos", f"DTSTAMP:{_ics_dt(utcnow())}", f"DTSTART:{_ics_dt(e.starts_at)}", f"DTEND:{_ics_dt(end)}",
                  f"SUMMARY:{_esc(e.title)}", f"DESCRIPTION:{_esc((e.description or '')[:500])}", f"LOCATION:{_esc(e.venue)}",
                  f"URL:{settings.base_url}/e/{e.slug}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(_fold(l) for l in lines) + "\r\n", media_type="text/calendar; charset=utf-8")


# ---- uploads (images only; local disk, swap for S3/R2 behind this one function) -------------

def sniff_image(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None  # SVG is deliberately NOT accepted: it can carry scripts


DOC_TYPES = {"pdf": "application/pdf", "txt": "text/plain", "csv": "text/csv",
             "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
OOXML_ROOT = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}


def sniff_document(data: bytes, filename: str) -> tuple[str, str] | None:
    """Documents are trusted by their BYTES, not their name: a renamed .exe or .html is refused. They are always served as downloads."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if data.startswith(b"%PDF-"):
        return DOC_TYPES["pdf"], "pdf"
    if data[:4] == b"PK\x03\x04" and ext in OOXML_ROOT:
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()   # reads the index only; nothing is extracted (no zip-bomb risk)
        except zipfile.BadZipFile:
            return None
        if len(names) <= 5000 and "[Content_Types].xml" in names and any(n.startswith(OOXML_ROOT[ext]) for n in names):
            return DOC_TYPES[ext], ext
        return None
    if ext in ("txt", "csv") and b"\x00" not in data:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return DOC_TYPES[ext], ext
    return None


def clean_filename(name: str) -> str:
    return re.sub(r"[^\w .()\-]", "_", os.path.basename(name or ""))[:120].strip() or "file"


UPLOAD_PERMS = ["files.manage", "posts.manage", "events.manage", "club.settings"]


@router.post("/uploads", status_code=201, dependencies=[Depends(rate_limit("upload", 40, 3600))])
async def upload(file: UploadFile, only: Literal["image", "any"] = "image", ctx: ClubCtx = Depends(club_perm_any(UPLOAD_PERMS)), db: Session = Depends(get_db)):
    img_cap, doc_cap = settings.max_upload_mb * 1024 * 1024, settings.max_document_mb * 1024 * 1024
    data = await file.read(max(img_cap, doc_cap) + 1)
    fname = clean_filename(file.filename or "")
    kind, sniffed = "image", sniff_image(data)  # trust the bytes, not the filename or client content-type
    if sniffed and len(data) > img_cap:
        raise HTTPException(413, f"Images must be under {settings.max_upload_mb} MB")
    if not sniffed and only == "any":
        kind, sniffed = "document", sniff_document(data, fname)
        if sniffed and len(data) > doc_cap:
            raise HTTPException(413, f"Documents must be under {settings.max_document_mb} MB")
    if not sniffed:
        raise HTTPException(415, "Allowed: PNG, JPEG, WebP images" + (", and PDF, Word, Excel, PowerPoint, TXT or CSV documents" if only == "any" else ""))
    if len(data) > max(img_cap, doc_cap):
        raise HTTPException(413, "File too large")
    limit_mb = get_limits(db, ctx.club).get("storage_mb")
    if limit_mb is not None and storage_used(db, ctx.club.id) + len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(402, {"code": "limit_reached", "limit": "storage_mb", "max": limit_mb,
                                  "message": f"Your plan includes {limit_mb} MB of storage. Delete files or upgrade."})
    name = f"{uuid.uuid4().hex}.{sniffed[1]}"
    up = Upload(club_id=ctx.club.id, user_id=ctx.user.id, stored_name=name, original_name=fname, content_type=sniffed[0], kind=kind, size=len(data))
    if settings.media_backend == "db":
        up.data = data
    else:
        folder = os.path.join(settings.media_dir, str(ctx.club.id))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(data)
    db.add(up)
    db.commit()
    return {"id": str(up.id), "url": f"/media/{ctx.club.id}/{name}", "size": len(data), "kind": kind, "name": fname, "content_type": sniffed[0]}


@router.get("/uploads")
def list_uploads(ctx: ClubCtx = Depends(club_perm("files.manage")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Upload).where(Upload.club_id == ctx.club.id).order_by(Upload.created_at.desc()).limit(200)).all()
    lim = get_limits(db, ctx.club).get("storage_mb")
    return {"used_bytes": storage_used(db, ctx.club.id), "limit_bytes": lim and lim * 1024 * 1024,
            "items": [{"id": str(u.id), "url": f"/media/{ctx.club.id}/{u.stored_name}", "size": u.size, "name": u.original_name, "kind": u.kind} for u in rows]}


@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: uuid.UUID, ctx: ClubCtx = Depends(club_perm("files.manage")), db: Session = Depends(get_db)):
    u = db.scalar(select(Upload).where(Upload.id == upload_id, Upload.club_id == ctx.club.id))
    if not u:
        raise HTTPException(404, "File not found")
    try:
        os.remove(os.path.join(settings.media_dir, str(ctx.club.id), u.stored_name))
    except FileNotFoundError:
        pass
    for p in db.scalars(select(Post).where(Post.club_id == ctx.club.id)):      # no dead links left on posts
        if any(a.get("id") == str(u.id) for a in (p.attachments or [])):
            p.attachments = [a for a in p.attachments if a.get("id") != str(u.id)]
    db.delete(u)
    db.commit()
    return {"ok": True}
