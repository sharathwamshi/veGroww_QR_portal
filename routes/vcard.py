import os
import re

from flask import (Blueprint, Response, current_app, flash, redirect,
                   render_template, request, send_from_directory, url_for)

from extensions import db
from models import VCard, VCardLink
from utils.decorators import login_required
from utils.url_helpers import public_url_for
from utils.file_helpers import (allowed_file, delete_if_exists,
                                safe_download_name, save_upload)
from utils.qr_utils import save_qr_for_url
from utils.vcard_utils import SOCIAL_PLATFORMS, build_vcf, unique_slug

vcard_bp = Blueprint("vcard", __name__, url_prefix="/vcard")

HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ---------------------------------------------------------------------
# Form parsing
# ---------------------------------------------------------------------
def _clean_color(value: str, default: str) -> str:
    value = (value or "").strip()
    return value if HEX_COLOR.match(value) else default


def _collect_links(form):
    """
    Read the repeatable rows out of the submitted form.

    Rows arrive as parallel lists — phone_value[], phone_label[] and so on —
    so a card can carry any number of each. Blank rows are dropped, and the
    submitted order becomes sort_order.
    """
    links = []
    order = 0

    for kind in ("phone", "email", "website"):
        values = form.getlist(f"{kind}_value")
        labels = form.getlist(f"{kind}_label")
        for index, value in enumerate(values):
            value = value.strip()
            if not value:
                continue
            links.append(
                VCardLink(
                    kind=kind,
                    value=value[:500],
                    label=(labels[index].strip()[:100] if index < len(labels) else None) or None,
                    sort_order=order,
                )
            )
            order += 1

    platforms = form.getlist("social_platform")
    values = form.getlist("social_value")
    labels = form.getlist("social_label")
    for index, value in enumerate(values):
        value = value.strip()
        if not value:
            continue
        platform = platforms[index].strip().lower() if index < len(platforms) else "website"
        links.append(
            VCardLink(
                kind="social",
                platform=platform if platform in SOCIAL_PLATFORMS else "website",
                value=value[:500],
                label=(labels[index].strip()[:100] if index < len(labels) else None) or None,
                sort_order=order,
            )
        )
        order += 1

    return links


def _apply_form(card, form):
    """Copy the scalar fields from the submitted form onto the card."""
    card.first_name = form.get("first_name", "").strip()[:100]
    card.last_name = form.get("last_name", "").strip()[:100] or None
    card.qr_name = (form.get("qr_name", "").strip() or card.first_name)[:150]

    card.primary_color = _clean_color(form.get("primary_color"), "#527AC9")
    card.secondary_color = _clean_color(form.get("secondary_color"), "#7EC09F")

    card.company = form.get("company", "").strip()[:200] or None
    card.profession = form.get("profession", "").strip()[:200] or None
    card.summary = form.get("summary", "").strip() or None

    card.address_line = form.get("address_line", "").strip()[:300] or None
    card.city = form.get("city", "").strip()[:120] or None
    card.state = form.get("state", "").strip()[:120] or None
    card.postal_code = form.get("postal_code", "").strip()[:20] or None
    card.country = form.get("country", "").strip()[:120] or None

    card.show_add_contact = form.get("show_add_contact") == "on"


def _regenerate_qr(card):
    """Point a fresh QR code at this card's public page."""
    if card.qr_filename:
        delete_if_exists(os.path.join(current_app.config["QR_DIR"], card.qr_filename))

    page_url = public_url_for("vcard.public_view", slug=card.slug)
    qr_filename, target_url, short_url = save_qr_for_url(
        page_url, current_app.config["QR_DIR"], filename_prefix="vcard"
    )
    card.qr_filename = qr_filename
    card.qr_target_url = target_url
    card.qr_short_url = short_url


def _save_image(card, file_storage):
    if not file_storage or not file_storage.filename:
        return True
    if not allowed_file(file_storage.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
        flash("Profile image must be a PNG, JPG, JPEG or WEBP file.", "error")
        return False
    if card.image_filename:
        delete_if_exists(os.path.join(current_app.config["VCARD_IMAGE_DIR"], card.image_filename))
    card.image_filename = save_upload(
        file_storage, current_app.config["VCARD_IMAGE_DIR"], prefix="vc_"
    )
    return True


# ---------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------
@vcard_bp.route("/")
@login_required
def list_view():
    cards = VCard.query.order_by(VCard.created_at.desc()).all()
    return render_template("vcard/list.html", cards=cards)


@vcard_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        if not request.form.get("first_name", "").strip():
            flash("Enter a name — it's the only field the card can't go without.", "error")
            return render_template(
                "vcard/form.html", card=None, form=request.form,
                platforms=SOCIAL_PLATFORMS, mode="create"
            )

        card = VCard()
        _apply_form(card, request.form)
        card.slug = unique_slug(
            request.form.get("slug") or card.full_name,
            lambda s: VCard.query.filter_by(slug=s).first() is not None,
        )

        if not _save_image(card, request.files.get("image")):
            return render_template(
                "vcard/form.html", card=None, form=request.form,
                platforms=SOCIAL_PLATFORMS, mode="create"
            )

        card.links = _collect_links(request.form)
        db.session.add(card)
        db.session.flush()      # assign card.id before the QR URL is built
        _regenerate_qr(card)
        db.session.commit()

        flash(f"vCard created for {card.full_name}.", "success")
        return redirect(url_for("vcard.list_view"))

    return render_template(
        "vcard/form.html", card=None, form=None, platforms=SOCIAL_PLATFORMS, mode="create"
    )


@vcard_bp.route("/<int:card_id>/edit", methods=["GET", "POST"])
@login_required
def edit(card_id):
    card = VCard.query.get_or_404(card_id)

    if request.method == "POST":
        if not request.form.get("first_name", "").strip():
            flash("Enter a name — it's the only field the card can't go without.", "error")
            return render_template(
                "vcard/form.html", card=card, form=request.form,
                platforms=SOCIAL_PLATFORMS, mode="edit"
            )

        _apply_form(card, request.form)
        if not _save_image(card, request.files.get("image")):
            return render_template(
                "vcard/form.html", card=card, form=request.form,
                platforms=SOCIAL_PLATFORMS, mode="edit"
            )

        if request.form.get("remove_image") == "on" and card.image_filename:
            delete_if_exists(
                os.path.join(current_app.config["VCARD_IMAGE_DIR"], card.image_filename)
            )
            card.image_filename = None

        # Replace the whole link set — simplest way to honour reordering,
        # edits and deletions in one submit.
        card.links = _collect_links(request.form)

        # The slug is part of every QR already printed, so it stays put.
        db.session.commit()
        flash(f"vCard updated for {card.full_name}.", "success")
        return redirect(url_for("vcard.list_view"))

    return render_template(
        "vcard/form.html", card=card, form=None, platforms=SOCIAL_PLATFORMS, mode="edit"
    )


@vcard_bp.route("/<int:card_id>/regenerate", methods=["POST"])
@login_required
def regenerate(card_id):
    card = VCard.query.get_or_404(card_id)
    _regenerate_qr(card)
    db.session.commit()
    flash("QR code regenerated. Reprint any material using the old code.", "success")
    return redirect(url_for("vcard.list_view"))


@vcard_bp.route("/<int:card_id>/delete", methods=["POST"])
@login_required
def delete(card_id):
    card = VCard.query.get_or_404(card_id)
    if card.image_filename:
        delete_if_exists(os.path.join(current_app.config["VCARD_IMAGE_DIR"], card.image_filename))
    if card.qr_filename:
        delete_if_exists(os.path.join(current_app.config["QR_DIR"], card.qr_filename))
    db.session.delete(card)
    db.session.commit()
    flash("vCard deleted. Its public page and QR no longer resolve.", "info")
    return redirect(url_for("vcard.list_view"))


@vcard_bp.route("/<int:card_id>/qr")
@login_required
def download_qr(card_id):
    card = VCard.query.get_or_404(card_id)
    if not card.qr_filename:
        flash("This vCard has no QR code yet — regenerate it first.", "error")
        return redirect(url_for("vcard.list_view"))
    return send_from_directory(
        current_app.config["QR_DIR"],
        card.qr_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(card.qr_name or card.full_name)}-vcard-qr.png",
    )


# ---------------------------------------------------------------------
# Public views (no login — this is what the QR opens)
# ---------------------------------------------------------------------
@vcard_bp.route("/image/<path:filename>")
def serve_image(filename):
    return send_from_directory(current_app.config["VCARD_IMAGE_DIR"], filename)


@vcard_bp.route("/preview/<int:card_id>")
@login_required
def preview(card_id):
    """Signed-in preview of the public page, reachable from the listing."""
    card = VCard.query.get_or_404(card_id)
    return render_template("vcard/public.html", card=card, is_preview=True)


# Public pages live at /vcard/v/<slug>. TinyURL shortens whatever this
# resolves to before it reaches the QR, so the printed code stays sparse.
@vcard_bp.route("/v/<slug>")
def public_view(slug):
    card = VCard.query.filter_by(slug=slug).first_or_404()
    return render_template("vcard/public.html", card=card, is_preview=False)


@vcard_bp.route("/v/<slug>/contact.vcf")
def contact_vcf(slug):
    """The 'Add contact' button — returns a downloadable .vcf."""
    card = VCard.query.filter_by(slug=slug).first_or_404()
    photo_url = (
        public_url_for("vcard.serve_image", filename=card.image_filename)
        if card.image_filename else ""
    )
    payload = build_vcf(
        card,
        photo_url=photo_url,
        page_url=public_url_for("vcard.public_view", slug=card.slug),
    )
    filename = f"{safe_download_name(card.full_name, 'contact')}.vcf"
    return Response(
        payload,
        mimetype="text/vcard; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )