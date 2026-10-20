from datetime import datetime

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from sqlalchemy import func, or_

from extensions import db
from models import User
from models.user import STATUS_ACTIVE, STATUS_DISABLED, STATUS_PENDING
from utils.access import (SIGNUP_APPROVAL, SIGNUP_CLOSED, SIGNUP_OPEN,
                          create_user, signup_mode)
from utils.security import (clear_failures, login_locked, password_problem,
                            register_failure, safe_next, valid_email)

auth_bp = Blueprint("auth", __name__)


def start_session(user: User, remember: bool = False):
    """Fresh session for this user (drops anything from before sign-in)."""
    csrf = session.get("_csrf_token")
    session.clear()
    if csrf:
        session["_csrf_token"] = csrf
    session["uid"] = user.id
    session["sv"] = user.session_version
    session.permanent = bool(remember)
    user.last_login_at = datetime.utcnow()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("dashboard.home"))

    next_url = safe_next(request.args.get("next"))
    identifier = ""

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        wait = login_locked(identifier)
        if wait:
            minutes = max(1, (wait + 59) // 60)
            flash(f"Too many unsuccessful attempts. Please wait {minutes} minute"
                  f"{'' if minutes == 1 else 's'} and try again.", "error")
            return render_template("login.html", identifier=identifier, next_url=next_url,
                                   signup_mode=signup_mode()), 429

        ident = identifier.lower()
        user = User.query.filter(
            or_(func.lower(User.username) == ident, func.lower(User.email) == ident)
        ).first() if ident else None

        # Same message whether the account exists or not.
        if user is None or not user.check_password(password):
            register_failure(identifier)
            flash("That email/username and password don't match. Check both and try again.", "error")
            return render_template("login.html", identifier=identifier, next_url=next_url,
                                   signup_mode=signup_mode()), 401

        clear_failures(identifier)

        if user.status == STATUS_PENDING:
            return render_template("auth_status.html", kind="pending", user=user)
        if user.status == STATUS_DISABLED:
            return render_template("auth_status.html", kind="disabled", user=user)

        start_session(user, remember)
        db.session.commit()
        flash(f"Welcome back, {user.name.split()[0]}!", "success")
        return redirect(next_url or url_for("dashboard.home"))

    return render_template("login.html", identifier=identifier, next_url=next_url,
                           signup_mode=signup_mode())


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user is not None:
        return redirect(url_for("dashboard.home"))

    mode = signup_mode()
    if mode == SIGNUP_CLOSED:
        return render_template("signup.html", closed=True, form=None, mode=mode)

    if request.method == "POST":
        form = request.form
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")

        error = None
        if len(name) < 2:
            error = "Enter your full name."
        elif not valid_email(email):
            error = "Enter a valid email address — you'll use it to sign in."
        else:
            error = password_problem(password, confirm)
        if error is None and User.query.filter(
            or_(func.lower(User.email) == email, func.lower(User.username) == email)
        ).first():
            error = "An account with this email already exists. Sign in instead, or ask your administrator to reset the password."

        if error:
            flash(error, "error")
            return render_template("signup.html", closed=False, form=form, mode=mode), 400

        status = STATUS_ACTIVE if mode == SIGNUP_OPEN else STATUS_PENDING
        user = create_user(name[:150], email, password, status=status)
        db.session.commit()

        if mode == SIGNUP_APPROVAL:
            return render_template("auth_status.html", kind="submitted", user=user)

        start_session(user)
        db.session.commit()
        flash(f"Welcome, {user.name.split()[0]}! Your account is ready.", "success")
        return redirect(url_for("dashboard.home"))

    return render_template("signup.html", closed=False, form=None, mode=mode)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You've been signed out.", "info")
    return redirect(url_for("auth.login"))
