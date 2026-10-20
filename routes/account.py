from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_

from extensions import db
from models import User
from utils.access import quota_status
from utils.decorators import login_required
from utils.modules import MODULE_KEYS
from utils.security import password_problem, valid_email

account_bp = Blueprint("account", __name__, url_prefix="/account")


def _context(**extra):
    user = g.user
    usage = [quota_status(user, key) for key in MODULE_KEYS]
    return dict(usage=usage, **extra)


@account_bp.route("/", methods=["GET"])
@login_required
def home():
    return render_template("account.html", **_context())


@account_bp.route("/profile", methods=["POST"])
@login_required
def update_profile():
    user = g.user
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()

    if len(name) < 2:
        flash("Enter your full name.", "error")
        return render_template("account.html", **_context()), 400

    if user.is_admin:
        # Admin signs in with the username; email is optional extra info.
        if email and not valid_email(email):
            flash("That email address doesn't look right.", "error")
            return render_template("account.html", **_context()), 400
    elif not valid_email(email):
        flash("Enter a valid email address — it's what you sign in with.", "error")
        return render_template("account.html", **_context()), 400

    if email:
        taken = User.query.filter(
            User.id != user.id,
            or_(func.lower(User.email) == email, func.lower(User.username) == email),
        ).first()
        if taken:
            flash("Another account already uses that email.", "error")
            return render_template("account.html", **_context()), 400

    user.name = name[:150]
    user.email = email or None
    if not user.is_admin:
        user.username = email   # regular users sign in with their email
    db.session.commit()
    flash("Profile saved.", "success")
    return redirect(url_for("account.home"))


@account_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    user = g.user
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not user.check_password(current):
        flash("Your current password isn't right.", "error")
        return render_template("account.html", **_context(open_password=True)), 400

    problem = password_problem(new, confirm)
    if problem:
        flash(problem, "error")
        return render_template("account.html", **_context(open_password=True)), 400
    if new == current:
        flash("Choose a password that's different from the current one.", "error")
        return render_template("account.html", **_context(open_password=True)), 400

    user.set_password(new)
    db.session.commit()
    # Keep THIS session signed in; every other session is now invalid.
    session["sv"] = user.session_version
    flash("Password changed. You've been signed out on any other devices.", "success")
    return redirect(url_for("account.home"))
