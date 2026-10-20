import re

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_from_directory, url_for)

from flask import g

from extensions import db
from models import UpiQR
from utils.access import get_owned_or_404, limit_response, owned, record_usage
from utils.cleanup import delete_upi_qr
from utils.decorators import login_required
from utils.file_helpers import safe_download_name
from utils.qr_utils import build_upi_uri, save_qr_for_raw_data

upi_qr_bp = Blueprint("upi_qr", __name__, url_prefix="/upi-qr")

UPI_ID_PATTERN = re.compile(r"^[\w.\-]{2,256}@[a-zA-Z]{2,64}$")


@upi_qr_bp.route("/")
@login_required
def list_view():
    items = owned(UpiQR).order_by(UpiQR.created_at.desc()).all()
    return render_template("upi_qr/list.html", items=items)


@upi_qr_bp.route("/new", methods=["GET", "POST"])
@login_required
def generate():
    blocked = limit_response("upi_qr")
    if blocked:
        return blocked

    if request.method == "POST":
        upi_id = request.form.get("upi_id", "").strip()
        payee_name = request.form.get("payee_name", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        note = request.form.get("note", "").strip()

        if not UPI_ID_PATTERN.match(upi_id):
            flash("Enter a valid UPI ID, e.g. yourname@okhdfcbank", "error")
            return render_template("upi_qr/generate.html", form=request.form)

        amount = None
        if amount_raw:
            try:
                amount = round(float(amount_raw), 2)
                if amount <= 0:
                    raise ValueError
            except ValueError:
                flash("Amount must be a positive number, or left blank.", "error")
                return render_template("upi_qr/generate.html", form=request.form)

        upi_uri = build_upi_uri(upi_id, payee_name, amount, note)
        qr_filename = save_qr_for_raw_data(upi_uri, current_app.config["QR_DIR"], filename_prefix="upiqr")

        record = UpiQR(
            owner_id=g.user.id,
            upi_id=upi_id,
            payee_name=payee_name or None,
            amount=amount,
            note=note or None,
            upi_uri=upi_uri,
            qr_filename=qr_filename,
        )
        db.session.add(record)
        record_usage(g.user, "upi_qr")
        db.session.commit()
        flash("UPI payment QR generated.", "success")
        return redirect(url_for("upi_qr.list_view"))

    return render_template("upi_qr/generate.html", form=None)


@upi_qr_bp.route("/<int:item_id>/qr")
@login_required
def download_qr(item_id):
    """Download the payment QR PNG, named after the payee or UPI ID."""
    record = get_owned_or_404(UpiQR, item_id)
    label = record.payee_name or record.upi_id
    return send_from_directory(
        current_app.config["QR_DIR"],
        record.qr_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(label)}-upi-qr.png",
    )


@upi_qr_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    record = get_owned_or_404(UpiQR, item_id)
    delete_upi_qr(record)
    db.session.commit()
    flash("UPI QR code deleted.", "info")
    return redirect(url_for("upi_qr.list_view"))