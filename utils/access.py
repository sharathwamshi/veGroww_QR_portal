"""
Who is signed in, what they may use, how much they have left, and
"is this record theirs?".

Ownership rule used everywhere: a record that isn't yours behaves exactly
like a record that doesn't exist (404), so nobody can probe for other
users' data by changing an id in the URL.
"""

from datetime import datetime

from flask import abort, g
from sqlalchemy import func

from extensions import db
from models import (AppSetting, Batch, DefaultPermission, IDCard, ImageQR,
                    Invitation, UpiQR, UrlQR, UsageLog, User, UserPermission,
                    VCard)
from models.user import (PERIOD_LIFETIME, PERIOD_MONTHLY, ROLE_ADMIN,
                         ROLE_USER, STATUS_ACTIVE, STATUS_PENDING)
from utils.modules import FALLBACK_DEFAULT_QUOTA, MODULE_KEYS, MODULES

SIGNUP_OPEN = "open"
SIGNUP_APPROVAL = "approval"
SIGNUP_CLOSED = "closed"
SIGNUP_MODES = (SIGNUP_APPROVAL, SIGNUP_OPEN, SIGNUP_CLOSED)

# Top-level owned models per module (ID cards are owned via their batch).
_OWNED_MODEL = {
    "vcard": VCard,
    "invitation": Invitation,
    "url_qr": UrlQR,
    "image_qr": ImageQR,
    "upi_qr": UpiQR,
}


# ---------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------
def current_user():
    return getattr(g, "user", None)


# ---------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------
def owned(model, user=None):
    """Query of `model` rows belonging to the user (default: signed-in)."""
    user = user or current_user()
    return model.query.filter(model.owner_id == user.id)


def owned_cards(user=None):
    user = user or current_user()
    return IDCard.query.join(Batch, IDCard.batch_id == Batch.id).filter(Batch.owner_id == user.id)


def get_owned_or_404(model, item_id):
    item = db.session.get(model, item_id)
    user = current_user()
    if item is None or user is None or item.owner_id != user.id:
        abort(404)
    return item


def get_owned_card_or_404(card_id):
    card = db.session.get(IDCard, card_id)
    user = current_user()
    if card is None or user is None or card.batch is None or card.batch.owner_id != user.id:
        abort(404)
    return card


# ---------------------------------------------------------------------
# Settings + defaults
# ---------------------------------------------------------------------
def signup_mode() -> str:
    mode = AppSetting.get("signup_mode", SIGNUP_APPROVAL)
    return mode if mode in SIGNUP_MODES else SIGNUP_APPROVAL


def _int_or_none(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def default_limit_period() -> str:
    value = AppSetting.get("default_limit_period", PERIOD_LIFETIME)
    return value if value in (PERIOD_LIFETIME, PERIOD_MONTHLY) else PERIOD_LIFETIME


def default_total_limit():
    return _int_or_none(AppSetting.get("default_total_limit"))


def default_permission_map() -> dict:
    """{module: (enabled, quota)} for every module, falling back sensibly."""
    rows = {row.module: row for row in DefaultPermission.query.all()}
    out = {}
    for key in MODULE_KEYS:
        row = rows.get(key)
        if row is None:
            out[key] = (True, FALLBACK_DEFAULT_QUOTA.get(key))
        else:
            out[key] = (bool(row.enabled), row.quota)
    return out


def apply_defaults(user: User):
    """Copy the current new-user defaults onto an account (overwrites)."""
    defaults = default_permission_map()
    existing = {p.module: p for p in user.permissions}
    for key, (enabled, quota) in defaults.items():
        perm = existing.get(key)
        if perm is None:
            perm = UserPermission(module=key)
            user.permissions.append(perm)
        perm.enabled = enabled
        perm.quota = quota
    user.limit_period = default_limit_period()
    user.total_limit = default_total_limit()


def create_user(name, email, password, status=STATUS_ACTIVE) -> User:
    email = (email or "").strip().lower()
    user = User(
        name=name.strip(),
        username=email,
        email=email,
        role=ROLE_USER,
        status=status,
    )
    user.set_password(password)
    apply_defaults(user)
    db.session.add(user)
    return user


# ---------------------------------------------------------------------
# Feature access + quota
# ---------------------------------------------------------------------
def effective_permission(user: User, module: str):
    """(enabled, quota) for this user and module. Admins: everything, unlimited."""
    if user is None:
        return False, 0
    if user.role == ROLE_ADMIN:
        return True, None
    perm = user.permission_for(module)
    if perm is None:
        enabled, quota = default_permission_map().get(module, (False, 0))
        return enabled, quota
    return bool(perm.enabled), perm.quota


def has_module(user: User, module: str) -> bool:
    return effective_permission(user, module)[0]


def period_start(user: User):
    """Start of the counting window, or None for lifetime counting."""
    if user.limit_period == PERIOD_MONTHLY:
        now = datetime.utcnow()
        return datetime(now.year, now.month, 1)
    return None


def next_reset(user: User):
    if user.limit_period != PERIOD_MONTHLY:
        return None
    now = datetime.utcnow()
    return datetime(now.year + (now.month // 12), (now.month % 12) + 1, 1)


def owned_count(user: User, module: str) -> int:
    """How many the user has right now (generated cards for ID cards)."""
    if module == "id_cards":
        return owned_cards(user).filter(IDCard.status == "generated").count()
    model = _OWNED_MODEL.get(module)
    return owned(model, user).count() if model else 0


def has_content(user: User, module: str) -> bool:
    """Does the user own anything in this module? (batches count for ID cards)"""
    if module == "id_cards":
        return owned(Batch, user).first() is not None
    model = _OWNED_MODEL.get(module)
    return bool(model) and owned(model, user).first() is not None


def used_count(user: User, module: str) -> int:
    """What counts against the limit in the user's current period."""
    start = period_start(user)
    if start is None:
        return owned_count(user, module)
    return (
        db.session.query(func.count(UsageLog.id))
        .filter(UsageLog.user_id == user.id,
                UsageLog.module == module,
                UsageLog.created_at >= start)
        .scalar() or 0
    )


def total_used(user: User) -> int:
    return sum(used_count(user, key) for key in MODULE_KEYS)


def quota_status(user: User, module: str) -> dict:
    """
    Everything the UI needs to describe a module's allowance.

    remaining is None when nothing caps it. It accounts for both the
    module's own limit and the account-wide total limit.
    """
    enabled, quota = effective_permission(user, module)
    used = used_count(user, module) if user else 0

    remaining = None if quota is None else max(quota - used, 0)
    capped_by_total = False
    if user is not None and user.role != ROLE_ADMIN and user.total_limit is not None:
        total_left = max(user.total_limit - total_used(user), 0)
        if remaining is None or total_left < remaining:
            remaining = total_left
            capped_by_total = True

    if quota:
        percent = min(int(round(used * 100.0 / quota)), 100)
    else:
        percent = 0

    return {
        "module": module,
        "enabled": enabled,
        "used": used,
        "limit": quota,
        "remaining": remaining,
        "unlimited": quota is None and not capped_by_total,
        "at_limit": enabled and remaining is not None and remaining <= 0,
        "capped_by_total": capped_by_total,
        "percent": percent,
        "period": user.limit_period if user else PERIOD_LIFETIME,
        "resets_on": next_reset(user) if user else None,
    }


def limit_message(status: dict) -> str:
    meta = MODULES.get(status["module"], {})
    unit = meta.get("unit", "items")
    if status["capped_by_total"]:
        base = "You've reached your account's overall limit"
    else:
        base = f"You've used {status['used']} of {status['limit']} {unit}"
    if status["period"] == PERIOD_MONTHLY and status["resets_on"]:
        return f"{base}. Your allowance resets on {status['resets_on'].strftime('%d %b %Y')}."
    return f"{base}. Delete something you no longer need, or ask your administrator for a higher limit."


def record_usage(user: User, module: str, count: int = 1):
    for _ in range(max(count, 0)):
        db.session.add(UsageLog(user_id=user.id, module=module))


# ---------------------------------------------------------------------
# Admin-facing summaries
# ---------------------------------------------------------------------
def user_overview(user: User) -> dict:
    """Per-module usage plus totals for the admin user list / detail."""
    modules = {key: quota_status(user, key) for key in MODULE_KEYS}
    lifetime_total = sum(owned_count(user, key) for key in MODULE_KEYS)
    near = [s for s in modules.values()
            if s["enabled"] and s["limit"] and s["percent"] >= 80]
    return {"modules": modules, "lifetime_total": lifetime_total, "near_limit": near}


def pending_users():
    return User.query.filter_by(status=STATUS_PENDING).order_by(User.created_at.asc()).all()


def limit_response(module: str):
    """
    If the signed-in user can't create another item in `module`, return a
    ready-to-send "limit reached" page; otherwise None.
    """
    from flask import render_template  # local: keeps this module import-light

    status = quota_status(current_user(), module)
    if status["at_limit"]:
        return render_template("limit_reached.html", status=status,
                               message=limit_message(status)), 403
    return None
