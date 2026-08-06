import os
import re

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_from_directory, url_for)

from extensions import db
from models import UrlQR
from utils.decorators import login_required
from utils.file_helpers import delete_if_exists, safe_download_name
from utils.qr_utils import save_qr_for_url

url_qr_bp = Blueprint("url_qr", __name__, url_prefix="/url-qr")

# Deliberately permissive: allows internal hostnames, ports and IPs, which a
# strict public-domain pattern would reject.
URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def _normalise(raw_url: str) -> str:
    """Prepend https:// when the user typed a bare domain."""
    url = (raw_url or "").strip()
    if url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url
    return url


@url_qr_bp.route("/")
@login_required
def list_view():
    items = UrlQR.query.order_by(UrlQR.created_at.desc()).all()
    return render_template("url_qr/list.html", items=items)


@url_qr_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        target_url = _normalise(request.form.get("target_url", ""))

        if not name:
            flash("Give the QR code a name so you can find it later.", "error")
            return render_template("url_qr/form.html", item=None, form=request.form, mode="create")

        if not URL_PATTERN.match(target_url):
            flash("Enter a valid web address, e.g. https://example.com/page", "error")
            return render_template("url_qr/form.html", item=None, form=request.form, mode="create")

        qr_filename, long_url, short_url = save_qr_for_url(
            target_url, current_app.config["QR_DIR"], filename_prefix="urlqr"
        )
        record = UrlQR(
            name=name[:150],
            target_url=long_url[:1000],
            short_url=short_url,
            qr_filename=qr_filename,
        )
        db.session.add(record)
        db.session.commit()

        flash(f'QR code created for "{record.name}".', "success")
        return redirect(url_for("url_qr.list_view"))

    return render_template("url_qr/form.html", item=None, form=None, mode="create")


@url_qr_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id):
    item = UrlQR.query.get_or_404(item_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        target_url = _normalise(request.form.get("target_url", ""))

        if not name:
            flash("Give the QR code a name so you can find it later.", "error")
            return render_template("url_qr/form.html", item=item, form=request.form, mode="edit")
        if not URL_PATTERN.match(target_url):
            flash("Enter a valid web address, e.g. https://example.com/page", "error")
            return render_template("url_qr/form.html", item=item, form=request.form, mode="edit")

        item.name = name[:150]

        # The QR encodes the destination directly, so a changed URL means a
        # new code — anything already printed points at the old address.
        if target_url != item.target_url:
            delete_if_exists(os.path.join(current_app.config["QR_DIR"], item.qr_filename))
            qr_filename, long_url, short_url = save_qr_for_url(
                target_url, current_app.config["QR_DIR"], filename_prefix="urlqr"
            )
            item.qr_filename = qr_filename
            item.target_url = long_url[:1000]
            item.short_url = short_url
            flash("URL changed, so a new QR code was generated. Reprint anything using the old one.", "warning")
        else:
            flash("QR code updated.", "success")

        db.session.commit()
        return redirect(url_for("url_qr.list_view"))

    return render_template("url_qr/form.html", item=item, form=None, mode="edit")


@url_qr_bp.route("/<int:item_id>/regenerate", methods=["POST"])
@login_required
def regenerate(item_id):
    item = UrlQR.query.get_or_404(item_id)
    delete_if_exists(os.path.join(current_app.config["QR_DIR"], item.qr_filename))
    qr_filename, long_url, short_url = save_qr_for_url(
        item.target_url, current_app.config["QR_DIR"], filename_prefix="urlqr"
    )
    item.qr_filename = qr_filename
    item.short_url = short_url
    db.session.commit()
    flash("QR code regenerated with a fresh short link.", "success")
    return redirect(url_for("url_qr.list_view"))


@url_qr_bp.route("/<int:item_id>/qr")
@login_required
def download_qr(item_id):
    item = UrlQR.query.get_or_404(item_id)
    return send_from_directory(
        current_app.config["QR_DIR"],
        item.qr_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(item.name)}-qr.png",
    )


@url_qr_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    item = UrlQR.query.get_or_404(item_id)
    delete_if_exists(os.path.join(current_app.config["QR_DIR"], item.qr_filename))
    db.session.delete(item)
    db.session.commit()
    flash("QR code deleted.", "info")
    return redirect(url_for("url_qr.list_view"))
