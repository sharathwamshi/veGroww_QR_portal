from flask import Blueprint, g, render_template

from models import Batch
from utils.access import has_content, has_module, owned, owned_count, quota_status
from utils.modules import MODULES

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def home():
    user = g.user
    if user is None:
        # Signed-out visitors get the public landing page; everyone else
        # goes straight to their own dashboard.
        from utils.access import signup_mode
        return render_template("landing.html", signup_mode=signup_mode())
    tiles = []
    for key, meta in MODULES.items():
        enabled = has_module(user, key)
        count = owned_count(user, key)
        if not enabled and not has_content(user, key):
            continue
        tiles.append({
            "key": key,
            "meta": meta,
            "count": count,
            "enabled": enabled,
            "quota": quota_status(user, key),
        })

    recent_batches = []
    if has_module(user, "id_cards") or has_content(user, "id_cards"):
        recent_batches = owned(Batch).order_by(Batch.created_at.desc()).limit(5).all()

    admin = None
    if user.is_admin:
        from routes.admin import admin_summary
        admin = admin_summary()

    return render_template(
        "dashboard.html", tiles=tiles, recent_batches=recent_batches, admin=admin,
    )
