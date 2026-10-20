from functools import wraps

from flask import abort, flash, g, redirect, request, url_for

from utils.security import safe_next


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if getattr(g, "user", None) is None:
            flash("Please sign in to continue.", "warning")
            target = safe_next(request.full_path.rstrip("?")) if request.method == "GET" else None
            return redirect(url_for("auth.login", next=target) if target else url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not g.user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped
