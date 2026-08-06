import os

from flask import (Blueprint, current_app, flash, redirect, render_template,
                    request, send_from_directory, url_for)

from extensions import db
from models import ImageQR
from utils.decorators import login_required
from utils.url_helpers import public_url_for
from utils.file_helpers import (allowed_file, delete_if_exists,
                                 safe_download_name, save_upload)
from utils.qr_utils import save_qr_for_url

image_qr_bp = Blueprint("image_qr", __name__, url_prefix="/image-qr")


@image_qr_bp.route("/")
@login_required
def list_view():
    items = ImageQR.query.order_by(ImageQR.created_at.desc()).all()
    return render_template("image_qr/list.html", items=items)


@image_qr_bp.route("/new", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        image = request.files.get("image")

        if not image or not image.filename:
            flash("Please choose an image to upload.", "error")
            return redirect(url_for("image_qr.upload"))

        if not allowed_file(image.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            flash("Only PNG, JPG, JPEG or WEBP images are supported.", "error")
            return redirect(url_for("image_qr.upload"))

        image_filename = save_upload(image, current_app.config["IMAGE_QR_SOURCE_DIR"], prefix="img_")
        if not title:
            title = image_filename

        image_url = public_url_for("image_qr.serve_image", filename=image_filename)
        qr_filename, target_url, short_url = save_qr_for_url(
            image_url, current_app.config["QR_DIR"], filename_prefix="imgqr"
        )

        record = ImageQR(
            title=title,
            image_filename=image_filename,
            qr_filename=qr_filename,
            target_url=target_url,
            short_url=short_url,
        )
        db.session.add(record)
        db.session.commit()
        flash("QR code generated for your image.", "success")
        return redirect(url_for("image_qr.list_view"))

    return render_template("image_qr/upload.html")


@image_qr_bp.route("/file/<path:filename>")
def serve_image(filename):
    """Public route: this is the exact link that gets embedded (and shortened) in the QR."""
    return send_from_directory(current_app.config["IMAGE_QR_SOURCE_DIR"], filename)


@image_qr_bp.route("/<int:item_id>/qr")
@login_required
def download_qr(item_id):
    """Download the QR code PNG itself, named after the item's title."""
    record = ImageQR.query.get_or_404(item_id)
    return send_from_directory(
        current_app.config["QR_DIR"],
        record.qr_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(record.title)}-qr.png",
    )


@image_qr_bp.route("/<int:item_id>/regenerate", methods=["POST"])
@login_required
def regenerate(item_id):
    record = ImageQR.query.get_or_404(item_id)
    delete_if_exists(os.path.join(current_app.config["QR_DIR"], record.qr_filename))

    image_url = public_url_for("image_qr.serve_image", filename=record.image_filename)
    qr_filename, target_url, short_url = save_qr_for_url(
        image_url, current_app.config["QR_DIR"], filename_prefix="imgqr"
    )
    record.qr_filename = qr_filename
    record.target_url = target_url
    record.short_url = short_url
    db.session.commit()
    flash("QR code regenerated.", "success")
    return redirect(url_for("image_qr.list_view"))


@image_qr_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    record = ImageQR.query.get_or_404(item_id)
    delete_if_exists(os.path.join(current_app.config["IMAGE_QR_SOURCE_DIR"], record.image_filename))
    delete_if_exists(os.path.join(current_app.config["QR_DIR"], record.qr_filename))
    db.session.delete(record)
    db.session.commit()
    flash("Image and its QR code were deleted.", "info")
    return redirect(url_for("image_qr.list_view"))