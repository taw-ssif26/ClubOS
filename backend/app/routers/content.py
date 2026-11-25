"""Posts + standalone forms."""
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ClubCtx, can_view_club, club_perm, current_user, current_user_optional, get_club_or_404, get_membership
from ..models import Form, Post, Submission, Upload, User, aware, utcnow
from ..services.core import audit, iso, to_utc
from ..services.forms import FormError, validate_answers, validate_schema
from ..services.plans import require_flag, uses_conditions

router = APIRouter(tags=["content"])


class PostIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    kind: Literal["announcement", "news", "update", "achievement", "recruitment", "article", "notice"] = "announcement"
    status: Literal["draft", "published"] = "draft"
    publish_at: AwareDatetime | None = None
    pinned: bool = False
    attachments: list[UUID] = Field(default_factory=list, max_length=10)   # ids from POST /clubs/{slug}/uploads?only=any


def build_attachments(db: Session, club_id, ids: list[UUID]) -> list[dict]:
    """Only files uploaded to THIS club can be attached (an id from another club is rejected), stored as a display snapshot."""
    ids = list(dict.fromkeys(ids))
    ups = {u.id: u for u in db.scalars(select(Upload).where(Upload.id.in_(ids), Upload.club_id == club_id))} if ids else {}
    if len(ups) != len(ids):
        raise HTTPException(422, "One or more attachments were not found in this club's files")
    return [{"id": str(i), "url": f"/media/{club_id}/{ups[i].stored_name}", "name": ups[i].original_name or ups[i].stored_name,
             "size": ups[i].size, "kind": ups[i].kind, "content_type": ups[i].content_type} for i in ids]


def post_out(p: Post) -> dict:
    return {"id": str(p.id), "title": p.title, "body": p.body, "kind": p.kind, "status": p.status,
            "publish_at": iso(p.publish_at), "pinned": p.pinned, "created_at": iso(p.created_at),
            "attachments": p.attachments or []}


@router.post("/clubs/{slug}/posts", status_code=201)
def create_post(body: PostIn, ctx: ClubCtx = Depends(club_perm("posts.manage")), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["publish_at"] = to_utc(data["publish_at"])
    data["attachments"] = build_attachments(db, ctx.club.id, body.attachments)
    p = Post(club_id=ctx.club.id, author_id=ctx.user.id, **data)
    db.add(p)
    db.flush()
    audit(db, ctx.club.id, ctx.user.id, "post.created", p.title[:80])
    db.commit()
    return post_out(p)


@router.patch("/clubs/{slug}/posts/{post_id}")
def update_post(post_id: UUID, body: PostIn, ctx: ClubCtx = Depends(club_perm("posts.manage")), db: Session = Depends(get_db)):
    p = db.scalar(select(Post).where(Post.id == post_id, Post.club_id == ctx.club.id))
    if not p:
        raise HTTPException(404, "Post not found")
    for k, v in body.model_dump().items():
        if k == "attachments":
            v = build_attachments(db, ctx.club.id, body.attachments)
        setattr(p, k, to_utc(v) if k == "publish_at" else v)
    audit(db, ctx.club.id, ctx.user.id, "post.updated", p.title[:80])
    db.commit()
    return post_out(p)


@router.delete("/clubs/{slug}/posts/{post_id}")
def delete_post(post_id: UUID, ctx: ClubCtx = Depends(club_perm("posts.manage")), db: Session = Depends(get_db)):
    p = db.scalar(select(Post).where(Post.id == post_id, Post.club_id == ctx.club.id))
    if not p:
        raise HTTPException(404, "Post not found")
    audit(db, ctx.club.id, ctx.user.id, "post.deleted", p.title[:80])
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.get("/clubs/{slug}/posts")
def list_posts(slug: str, drafts: bool = False, limit: int = 20, offset: int = 0,
               user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    club = get_club_or_404(db, slug)
    m = get_membership(db, club.id, user.id if user else None)
    if not can_view_club(db, club, user, m):
        raise HTTPException(404, "Club not found")
    q = select(Post).where(Post.club_id == club.id)
    from ..permissions import has_perm
    if drafts and has_perm(m, "posts.manage"):
        pass
    else:
        q = q.where(Post.status == "published", or_(Post.publish_at.is_(None), Post.publish_at <= utcnow()))
    rows = db.scalars(q.order_by(Post.pinned.desc(), Post.created_at.desc()).limit(min(limit, 50)).offset(offset)).all()
    return [post_out(p) for p in rows]


# ---- standalone forms ----------------------------------------------------------------------

class FormIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field("", max_length=3000)
    fields: list
    is_open: bool = True
    closes_at: AwareDatetime | None = None
    max_submissions: int | None = Field(None, ge=1)


def form_out(f: Form, n: int | None = None) -> dict:
    d = {"id": str(f.id), "title": f.title, "description": f.description, "fields": f.fields, "is_open": f.is_open,
         "closes_at": iso(f.closes_at), "max_submissions": f.max_submissions}
    if n is not None:
        d["submissions"] = n
    return d


@router.post("/clubs/{slug}/forms", status_code=201)
def create_form(body: FormIn, ctx: ClubCtx = Depends(club_perm("forms.manage")), db: Session = Depends(get_db)):
    try:
        fields = validate_schema(body.fields)
    except FormError as e:
        raise HTTPException(422, {"errors": e.errors})
    if uses_conditions(fields):
        require_flag(db, ctx.club, "conditional_logic")
    f = Form(club_id=ctx.club.id, title=body.title, description=body.description, fields=fields, is_open=body.is_open,
             closes_at=to_utc(body.closes_at), max_submissions=body.max_submissions)
    db.add(f)
    db.flush()
    audit(db, ctx.club.id, ctx.user.id, "form.created", f.title)
    db.commit()
    return form_out(f, 0)


@router.get("/clubs/{slug}/forms")
def list_forms(ctx: ClubCtx = Depends(club_perm("forms.manage")), db: Session = Depends(get_db)):
    forms = db.scalars(select(Form).where(Form.club_id == ctx.club.id).order_by(Form.created_at.desc())).all()
    counts = dict(db.execute(select(Submission.form_id, func.count()).where(Submission.form_id.in_([f.id for f in forms])).group_by(Submission.form_id)).all())
    return [form_out(f, counts.get(f.id, 0)) for f in forms]


@router.get("/forms/{form_id}")
def get_form(form_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Only members of the owning club can fetch/fill a form."""
    f = db.get(Form, form_id)
    m = get_membership(db, f.club_id, user.id) if f else None
    if not f or not m or m.status != "active":
        raise HTTPException(404, "Form not found")
    return form_out(f)


@router.post("/forms/{form_id}/submit", status_code=201)
def submit_form(form_id: UUID, answers: dict = Body(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = db.scalar(select(Form).where(Form.id == form_id).with_for_update())
    m = get_membership(db, f.club_id, user.id) if f else None
    if not f or not m or m.status != "active":
        raise HTTPException(404, "Form not found")
    if not f.is_open or (f.closes_at and aware(f.closes_at) <= utcnow()):
        raise HTTPException(409, "This form is closed")
    if db.scalar(select(Submission.id).where(Submission.form_id == f.id, Submission.user_id == user.id)):
        raise HTTPException(409, "You already submitted this form")
    if f.max_submissions and db.scalar(select(func.count()).select_from(Submission).where(Submission.form_id == f.id)) >= f.max_submissions:
        raise HTTPException(409, "This form is full")
    try:
        data = validate_answers(f.fields, answers)
    except FormError as e:
        raise HTTPException(422, {"errors": e.errors})
    db.add(Submission(form_id=f.id, user_id=user.id, data=data))
    db.commit()
    return {"ok": True}


@router.get("/clubs/{slug}/forms/{form_id}/submissions")
def submissions(form_id: UUID, ctx: ClubCtx = Depends(club_perm("forms.manage")), db: Session = Depends(get_db)):
    f = db.scalar(select(Form).where(Form.id == form_id, Form.club_id == ctx.club.id))
    if not f:
        raise HTTPException(404, "Form not found")
    rows = db.scalars(select(Submission).where(Submission.form_id == f.id).order_by(Submission.created_at)).unique().all()
    return [{"user": {"username": s.user.username, "full_name": s.user.full_name}, "data": s.data, "at": iso(s.created_at)} for s in rows]
