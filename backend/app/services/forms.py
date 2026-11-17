"""Form schema + answer validation, shared by event registration, membership
applications and standalone forms. Conditional logic: show_if = {"field": id, "equals": value}."""
import re
from datetime import date

FIELD_TYPES = {"text", "textarea", "number", "email", "phone", "dropdown", "radio", "checkbox", "date", "agreement"}
CHOICE = {"dropdown", "radio", "checkbox"}
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{6,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FormError(ValueError):
    def __init__(self, errors: dict):
        super().__init__("invalid form")
        self.errors = errors


def validate_schema(fields: list) -> list:
    if not isinstance(fields, list) or len(fields) > 50:
        raise FormError({"_schema": "fields must be a list of at most 50 items"})
    seen: list[str] = []
    out = []
    for f in fields:
        if not isinstance(f, dict):
            raise FormError({"_schema": "each field must be an object"})
        fid, ftype = f.get("id"), f.get("type")
        if not isinstance(fid, str) or not ID_RE.match(fid) or fid in seen:
            raise FormError({"_schema": f"invalid or duplicate field id: {fid!r}"})
        if ftype not in FIELD_TYPES:
            raise FormError({fid: f"unknown type {ftype!r}"})
        label = str(f.get("label", "")).strip()
        if not label or len(label) > 200:
            raise FormError({fid: "label is required (max 200 chars)"})
        clean = {"id": fid, "type": ftype, "label": label, "required": bool(f.get("required", False))}
        if ftype in CHOICE:
            opts = f.get("options")
            if not isinstance(opts, list) or not opts or len(opts) > 50 or not all(isinstance(o, str) and o for o in opts):
                raise FormError({fid: "options must be a non-empty list of strings"})
            clean["options"] = opts
        show_if = f.get("show_if")
        if show_if is not None:
            if not isinstance(show_if, dict) or show_if.get("field") not in seen or "equals" not in show_if:
                raise FormError({fid: "show_if must reference an earlier field and include 'equals'"})
            clean["show_if"] = {"field": show_if["field"], "equals": show_if["equals"]}
        seen.append(fid)
        out.append(clean)
    return out


def validate_answers(fields: list, answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise FormError({"_answers": "answers must be an object"})
    errors: dict[str, str] = {}
    cleaned: dict = {}
    for f in fields:
        fid, ftype = f["id"], f["type"]
        cond = f.get("show_if")
        if cond and cleaned.get(cond["field"]) != cond["equals"]:
            continue  # hidden by conditional logic: ignore any submitted value
        val = answers.get(fid)
        empty = val is None or val == "" or val == [] or (ftype == "agreement" and val is not True)
        if empty:
            if f.get("required"):
                errors[fid] = "required"
            continue
        try:
            cleaned[fid] = _coerce(f, val)
        except ValueError as e:
            errors[fid] = str(e)
    if errors:
        raise FormError(errors)
    return cleaned


def _coerce(f: dict, val):
    t = f["type"]
    if t in ("text", "textarea"):
        if not isinstance(val, str):
            raise ValueError("must be text")
        if len(val) > (5000 if t == "textarea" else 500):
            raise ValueError("too long")
        return val.strip()
    if t == "number":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError("must be a number")
        return val
    if t == "email":
        if not isinstance(val, str) or not EMAIL_RE.match(val) or len(val) > 255:
            raise ValueError("invalid email")
        return val.lower()
    if t == "phone":
        if not isinstance(val, str) or not PHONE_RE.match(val):
            raise ValueError("invalid phone number")
        return val
    if t in ("dropdown", "radio"):
        if val not in f["options"]:
            raise ValueError("not a valid option")
        return val
    if t == "checkbox":
        if not isinstance(val, list) or not all(v in f["options"] for v in val):
            raise ValueError("invalid selection")
        return list(dict.fromkeys(val))
    if t == "date":
        try:
            date.fromisoformat(val)
        except (TypeError, ValueError):
            raise ValueError("date must be YYYY-MM-DD")
        return val
    if t == "agreement":
        return True
    raise ValueError("unsupported field")
