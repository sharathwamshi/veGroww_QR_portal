"""
Admin: user management, per-user feature access and limits, new-user
defaults and the signup setting.

Admins see each account's details and usage counts — never the content
of other users' QR codes, cards or pages.
"""

from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from extensions import db
from models import AppSetting, DefaultPermission, User, UserPermission
from models.user import (PERIOD_LIFETIME, PERIOD_MONTHLY, ROLE_ADMIN,
                         STATUS_ACTIVE, STATUS_DISABLED, STATUS_PENDING)
from utils.access import (SIGNUP_MODES, apply_defaults,
                          create_user, default_limit_period,
                          default_permission_map, default_total_limit,
                          signup_mode, user_overview)
from utils.cleanup import delete_everything_owned_by
from utils.decorators import admin_required
from utils.modules import MODULE_KEYS, MODULES
from utils.security import password_problem, valid_email

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

STATUS_LABELS = {
    STATUS_ACTIVE: "Active",
    STATUS_PENDING: "Awaiting approval",
    STATUS_DISABLED: "Disabled",
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _get_user_or_404(user_id) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    return user


def _parse_limit(raw):
    """'' -> (True, None) unlimited; '12' -> (True, 12); bad -> (False, None)."""
    raw = (raw or "").strip()
    if raw == "":
        return True, None
    try:
        value = int(raw)
    except ValueError:
        return False, None
    if value < 0 or value > 1_000_000:
        return False, None
    return True, value


def _read_access_grid(form):
    """Parse the module grid from a submitted form. Returns (grid, error)."""
    grid = {}
    for key in MODULE_KEYS:
        enabled = form.get(f"enabled_{key}") == "on"
        ok, quota = _parse_limit(form.get(f"quota_{key}"))
        if not ok:
            return None, f"The limit for {MODULES[key]['label']} must be a whole number (or blank for unlimited)."
        grid[key] = (enabled, quota)

    period = form.get("limit_period", PERIOD_LIFETIME)
    if period not in (PERIOD_LIFETIME, PERIOD_MONTHLY):
        period = PERIOD_LIFETIME
    ok, total = _parse_limit(form.get("total_limit"))
    if not ok:
        return None, "The overall limit must be a whole number (or blank for no overall limit)."
    return {"modules": grid, "period": period, "total": total}, None


def _is_self(user: User) -> bool:
    return user.id == g.user.id


# ---------------------------------------------------------------------
# Users list
# ---------------------------------------------------------------------
@admin_bp.route("/users")
@admin_required
def users():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")

    query = User.query
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(or_(func.lower(User.name).like(like),
                                 func.lower(User.email).like(like),
                                 func.lower(User.username).like(like)))
    if status in STATUS_LABELS:
        query = query.filter(User.status == status)

    rows = query.order_by(
        (User.role == ROLE_ADMIN).desc(),
        (User.status == STATUS_PENDING).desc(),
        User.created_at.desc(),
    ).all()

    counts = dict(
        db.session.query(User.status, func.count(User.id)).group_by(User.status).all()
    )
    return render_template(
        "admin/users.html",
        rows=[(u, user_overview(u)) for u in rows],
        q=q, status=status, counts=counts, total=sum(counts.values()),
        status_labels=STATUS_LABELS,
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def user_new():
    if request.method == "POST":
        form = request.form
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")

        error = None
        if len(name) < 2:
            error = "Enter the person's full name."
        elif not valid_email(email):
            error = "Enter a valid email address — they'll use it to sign in."
        else:
            error = password_problem(password)
        if error is None and User.query.filter(
            or_(func.lower(User.email) == email, func.lower(User.username) == email)
        ).first():
            error = "An account with this email already exists."

        if error:
            flash(error, "error")
            return render_template("admin/user_new.html", form=form), 400

        user = create_user(name[:150], email, password, status=STATUS_ACTIVE)
        db.session.commit()
        flash(f"Account created for {user.name}. Share the email and temporary password with them — "
              "they can change the password from My account.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    return render_template("admin/user_new.html", form=None)


# ---------------------------------------------------------------------
# User detail + actions
# ---------------------------------------------------------------------
@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = _get_user_or_404(user_id)
    overview = user_overview(user)
    return render_template(
        "admin/user_detail.html",
        user=user,
        overview=overview,
        values={k: (st["enabled"], st["limit"]) for k, st in overview["modules"].items()},
        status_labels=STATUS_LABELS,
        is_self=_is_self(user),
        defaults=default_permission_map(),
    )


@admin_bp.route("/users/<int:user_id>/profile", methods=["POST"])
@admin_required
def user_profile(user_id):
    user = _get_user_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Edit the administrator's own details from My account.", "info")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if len(name) < 2 or not valid_email(email):
        flash("Enter a full name and a valid email address.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    taken = User.query.filter(
        User.id != user.id,
        or_(func.lower(User.email) == email, func.lower(User.username) == email),
    ).first()
    if taken:
        flash("Another account already uses that email.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    user.name = name[:150]
    user.email = email
    user.username = email
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/status", methods=["POST"])
@admin_required
def user_status(user_id):
    user = _get_user_or_404(user_id)
    new_status = request.form.get("status", "")
    if user.role == ROLE_ADMIN:
        flash("The administrator account can't be disabled.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))
    if new_status not in STATUS_LABELS or new_status == STATUS_PENDING:
        abort(400)

    previous = user.status
    user.status = new_status
    if new_status == STATUS_DISABLED:
        user.session_version += 1      # signs them out everywhere, immediately
    db.session.commit()

    if previous == STATUS_PENDING and new_status == STATUS_ACTIVE:
        flash(f"{user.name} is approved and can sign in now.", "success")
    elif new_status == STATUS_ACTIVE:
        flash(f"{user.name}'s account is active again.", "success")
    else:
        flash(f"{user.name}'s account is disabled and they've been signed out. "
              "Their public pages and QR codes keep working.", "info")

    back = request.form.get("back")
    if back == "list":
        return redirect(url_for("admin.users"))
    if back == "dashboard":
        return redirect(url_for("dashboard.home"))
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/access", methods=["POST"])
@admin_required
def user_access(user_id):
    user = _get_user_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("Administrators always have every feature with no limits.", "info")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    parsed, error = _read_access_grid(request.form)
    if error:
        flash(error, "error")
        return redirect(url_for("admin.user_detail", user_id=user.id) + "#access")

    existing = {p.module: p for p in user.permissions}
    for key, (enabled, quota) in parsed["modules"].items():
        perm = existing.get(key)
        if perm is None:
            perm = UserPermission(module=key)
            user.permissions.append(perm)
        perm.enabled = enabled
        perm.quota = quota
    user.limit_period = parsed["period"]
    user.total_limit = parsed["total"]
    db.session.commit()
    flash("Access and limits saved. They apply to this user straight away.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id) + "#access")


@admin_bp.route("/users/<int:user_id>/apply-defaults", methods=["POST"])
@admin_required
def user_apply_defaults(user_id):
    user = _get_user_or_404(user_id)
    if user.role == ROLE_ADMIN:
        abort(400)
    apply_defaults(user)
    db.session.commit()
    flash("This user now has the current new-user defaults.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id) + "#access")


@admin_bp.route("/users/<int:user_id>/password", methods=["POST"])
@admin_required
def user_password(user_id):
    user = _get_user_or_404(user_id)
    if _is_self(user):
        flash("Change your own password from My account.", "info")
        return redirect(url_for("account.home"))

    new = request.form.get("new_password", "")
    problem = password_problem(new, request.form.get("confirm_password", ""))
    if problem:
        flash(problem, "error")
        return redirect(url_for("admin.user_detail", user_id=user.id) + "#password")

    user.set_password(new)          # also signs them out of existing sessions
    db.session.commit()
    flash(f"Password reset for {user.name}. Share the new password with them securely; "
          "they can change it from My account.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def user_delete(user_id):
    user = _get_user_or_404(user_id)
    if user.role == ROLE_ADMIN:
        flash("The administrator account can't be deleted.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    typed = request.form.get("confirm", "").strip().lower()
    if typed != (user.email or user.username).lower():
        flash("To delete, type the account's email exactly as shown.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id) + "#danger")

    name = user.name
    removed = delete_everything_owned_by(user)
    db.session.flush()              # records first, so the owner FK never blocks
    db.session.delete(user)         # permissions + usage go with it (cascade)
    db.session.commit()
    flash(f"Deleted {name}'s account and {removed} item{'' if removed == 1 else 's'}.", "info")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------
# Settings: signup + new-user defaults
# ---------------------------------------------------------------------
@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        mode = request.form.get("signup_mode", "")
        if mode not in SIGNUP_MODES:
            flash("Choose how new people can join.", "error")
            return redirect(url_for("admin.settings"))

        parsed, error = _read_access_grid(request.form)
        if error:
            flash(error, "error")
            return redirect(url_for("admin.settings"))

        AppSetting.put("signup_mode", mode)
        AppSetting.put("default_limit_period", parsed["period"])
        AppSetting.put("default_total_limit", parsed["total"])
        rows = {r.module: r for r in DefaultPermission.query.all()}
        for key, (enabled, quota) in parsed["modules"].items():
            row = rows.get(key)
            if row is None:
                row = DefaultPermission(module=key)
                db.session.add(row)
            row.enabled = enabled
            row.quota = quota
        db.session.commit()
        flash("Settings saved. New defaults apply to accounts created from now on — "
              "existing users keep their current access.", "success")
        return redirect(url_for("admin.settings"))

    return render_template(
        "admin/settings.html",
        mode=signup_mode(),
        defaults=default_permission_map(),
        period=default_limit_period(),
        total=default_total_limit(),
    )


def admin_summary():
    """Numbers for the admin panel on the dashboard."""
    week_ago = datetime.utcnow() - timedelta(days=7)
    regular = User.query.filter(User.role != ROLE_ADMIN)
    users = regular.order_by(User.created_at.desc()).all()
    near = []
    for u in users:
        if u.status != STATUS_ACTIVE:
            continue
        ov = user_overview(u)
        if ov["near_limit"]:
            near.append((u, ov["near_limit"]))
    return {
        "users": len(users),
        "active": sum(1 for u in users if u.status == STATUS_ACTIVE),
        "pending": [u for u in users if u.status == STATUS_PENDING],
        "disabled": sum(1 for u in users if u.status == STATUS_DISABLED),
        "new_week": sum(1 for u in users if u.created_at and u.created_at >= week_ago),
        "near_limit": near[:8],
        "signup_mode": signup_mode(),
    }
