import logging
import os
from datetime import timedelta

from flask import (Flask, g, redirect, render_template, request,
                   send_from_directory, session, url_for)

from config import Config
from extensions import db

log = logging.getLogger(__name__)


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Session cookie hardening. SESSION_COOKIE_SECURE is opt-in via .env
    # because the app is often opened over plain http on a LAN.
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=app.config.get("REMEMBER_ME_DAYS", 30))

    # Make sure every local storage folder exists on startup
    for folder in (
        app.config["PHOTO_DIR"],
        app.config["LOGO_DIR"],
        app.config["SIGNATURE_DIR"],
        app.config["ID_CARD_DIR"],
        app.config["QR_DIR"],
        app.config["IMAGE_QR_SOURCE_DIR"],
        app.config["VCARD_IMAGE_DIR"],
        app.config["INVITE_IMAGE_DIR"],
    ):
        os.makedirs(folder, exist_ok=True)

    db.init_app(app)

    # ---- Blueprints ----
    from routes.account import account_bp
    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.id_cards import id_cards_bp
    from routes.image_qr import image_qr_bp
    from routes.invitation import invitation_bp
    from routes.upi_qr import upi_qr_bp
    from routes.url_qr import url_qr_bp
    from routes.vcard import vcard_bp

    for bp in (auth_bp, account_bp, admin_bp, dashboard_bp, id_cards_bp, image_qr_bp,
               upi_qr_bp, vcard_bp, url_qr_bp, invitation_bp):
        app.register_blueprint(bp)

    _register_request_hooks(app)
    _register_template_helpers(app)
    _register_media_routes(app)
    _register_error_pages(app)

    if app.config["SECRET_KEY"] == Config.DEFAULT_SECRET_KEY:
        log.warning("SECRET_KEY is still the default value - set a long random SECRET_KEY in .env.")

    from utils import bootstrap
    bootstrap.run(app)

    return app


# ---------------------------------------------------------------------
# Per-request: who is signed in, CSRF, module access
# ---------------------------------------------------------------------
def _register_request_hooks(app):
    from models import User
    from utils.access import has_content, has_module
    from utils.modules import MODULE_KEYS, PUBLIC_ENDPOINTS, WRITE_FORM_ENDPOINTS
    from utils.security import csrf_valid

    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("uid")
        if uid is None:
            return
        user = db.session.get(User, uid)
        # Signed out if the account is gone, no longer active, or its
        # password changed / it was disabled after this session started.
        if user is None or not user.is_active or session.get("sv") != user.session_version:
            session.pop("uid", None)
            session.pop("sv", None)
            return
        g.user = user

    @app.before_request
    def check_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not csrf_valid():
            return render_template(
                "error.html", code=400, title="This page has expired",
                message="For your security the form timed out. Go back, refresh the page and try again.",
            ), 400

    @app.before_request
    def gate_modules():
        module = request.blueprint
        if module not in MODULE_KEYS or request.endpoint in PUBLIC_ENDPOINTS:
            return
        if g.user is None:
            # Routes carry @login_required too; this just keeps the rule central.
            return redirect(url_for("auth.login"))

        g.module_readonly = False
        if has_module(g.user, module):
            return

        # Module switched off by the admin. Keep what they made reachable
        # (view + download), but nothing that creates or changes things.
        is_read = request.method == "GET" and request.endpoint not in WRITE_FORM_ENDPOINTS
        if is_read and has_content(g.user, module):
            g.module_readonly = True
            return
        return render_template("module_unavailable.html", module=module), 403


# ---------------------------------------------------------------------
# Template globals / filters
# ---------------------------------------------------------------------
def _register_template_helpers(app):
    from models import User
    from utils.access import has_content, has_module, quota_status
    from utils.modules import MODULES
    from utils.security import csrf_field, safe_href
    from utils.vcard_utils import platform_meta

    app.add_template_filter(safe_href, "safe_href")

    @app.context_processor
    def inject_globals():
        user = getattr(g, "user", None)

        nav = []
        if user is not None:
            for key, meta in MODULES.items():
                enabled = has_module(user, key)
                if enabled or has_content(user, key):
                    nav.append({"key": key, "meta": meta, "readonly": not enabled})

        def quota(module):
            return quota_status(user, module) if user is not None else None

        pending = 0
        if user is not None and user.is_admin:
            from models.user import STATUS_PENDING
            pending = User.query.filter_by(status=STATUS_PENDING).count()

        return {
            "app_name": app.config["APP_NAME"],
            "app_tagline": app.config["APP_TAGLINE"],
            "platform_meta": platform_meta,
            "current_user": user,
            "nav_modules": nav,
            "modules": MODULES,
            "quota": quota,
            "module_readonly": getattr(g, "module_readonly", False),
            "csrf_field": csrf_field,
            "admin_pending_count": pending,
        }


# ---------------------------------------------------------------------
# Local file serving for generated/uploaded assets.
# These stay public: QR images and photos are what public verification
# and invitation pages display. File names are random, so they can't be
# listed or guessed.
# ---------------------------------------------------------------------
def _register_media_routes(app):
    @app.route("/media/photos/<path:filename>")
    def media_photo(filename):
        return send_from_directory(app.config["PHOTO_DIR"], filename)

    @app.route("/media/logos/<path:filename>")
    def media_logo(filename):
        return send_from_directory(app.config["LOGO_DIR"], filename)

    @app.route("/media/signatures/<path:filename>")
    def media_signature(filename):
        return send_from_directory(app.config["SIGNATURE_DIR"], filename)

    @app.route("/media/id-cards/<path:filename>")
    def media_card(filename):
        return send_from_directory(app.config["ID_CARD_DIR"], filename)

    @app.route("/media/qr/<path:filename>")
    def media_qr(filename):
        return send_from_directory(app.config["QR_DIR"], filename)


def _register_error_pages(app):
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template(
            "error.html", code=403, title="You don't have access to this page",
            message="This area is limited to administrators.",
        ), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template(
            "error.html", code=404, title="Page not found",
            message="The page you're looking for doesn't exist, or it isn't yours to view.",
        ), 404

    @app.errorhandler(413)
    def too_large(_e):
        limit = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        return render_template(
            "error.html", code=413, title="That file is too large",
            message=f"Uploads can be up to {limit} MB. Try a smaller or compressed file.",
        ), 413


if __name__ == "__main__":
    application = create_app()
    application.run(
        debug=application.config["FLASK_DEBUG"],
        host=application.config["FLASK_HOST"],
        port=application.config["FLASK_PORT"],
    )
