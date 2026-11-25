PERMS = [
    "club.settings",
    "members.view",
    "members.manage",
    "roles.manage",
    "events.manage",
    "registrations.manage",
    "attendance.manage",
    "forms.manage",
    "posts.manage",
    "comms.send",
    "analytics.view",
    "audit.view",
    "files.manage",
    "points.manage",
]

# (name, permissions, rank). Rank gates who may modify whom.
DEFAULT_ROLES = [
    ("Owner", ["*"], 100),
    ("Administrator", list(PERMS), 90),
    ("Executive", ["members.view", "events.manage", "registrations.manage", "attendance.manage",
                   "forms.manage", "posts.manage", "comms.send", "analytics.view", "files.manage", "points.manage"], 70),
    ("Event manager", ["events.manage", "registrations.manage", "attendance.manage", "members.view", "files.manage"], 50),
    ("Member manager", ["members.view", "members.manage"], 50),
    ("Content manager", ["posts.manage", "files.manage"], 50),
    ("Volunteer", ["attendance.manage"], 20),
    ("Member", [], 10),
]

ADMIN_RANK = 50  # roles at/above this rank occupy an "admin seat" for plan limits


def perms_of(role) -> set[str]:
    return set(role.permissions or [])


def has_perm(membership, perm: str) -> bool:
    if membership is None or membership.status != "active":
        return False
    perms = membership.role.permissions or []
    return "*" in perms or perm in perms
