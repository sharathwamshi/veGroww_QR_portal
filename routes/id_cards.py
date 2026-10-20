import os

from flask import (Blueprint, current_app, flash, redirect, render_template,
                    request, send_from_directory, url_for)

import uuid

from flask import g
from werkzeug.utils import secure_filename

from extensions import db
from models import Batch, IDCard
from utils.access import (get_owned_card_or_404, get_owned_or_404, limit_message,
                          owned, quota_status, record_usage)
from utils.bulk_import import read_bulk_file
from utils.cleanup import delete_batch, remove_card_files
from utils.url_helpers import public_url_for
from utils.decorators import login_required
from utils.file_helpers import (allowed_file, delete_if_exists,
                                 safe_download_name, save_upload)
from utils.id_card_render import render_id_card, paste_qr_on_card
from utils.qr_utils import save_qr_for_url

id_cards_bp = Blueprint("id_cards", __name__, url_prefix="/id-cards")


# ---------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------
@id_cards_bp.route("/")
@login_required
def batches():
    all_batches = owned(Batch).order_by(Batch.created_at.desc()).all()
    return render_template("id_cards/batches.html", batches=all_batches)


@id_cards_bp.route("/batch/new", methods=["GET", "POST"])
@login_required
def batch_new():
    if request.method == "POST":
        batch = Batch(
            owner_id=g.user.id,
            name=request.form["name"].strip(),
            company_name=request.form["company_name"].strip(),
            company_address=request.form["company_address"].strip(),
            signature_label=request.form.get("signature_label", "Issuing Authority").strip() or "Issuing Authority",
        )
        logo = request.files.get("logo")
        if logo and logo.filename and allowed_file(logo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            batch.logo_filename = save_upload(logo, current_app.config["LOGO_DIR"], prefix="logo_")

        signature = request.files.get("signature")
        if signature and signature.filename and allowed_file(signature.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            batch.signature_filename = save_upload(signature, current_app.config["SIGNATURE_DIR"], prefix="sig_")

        db.session.add(batch)
        db.session.commit()
        flash(f'Batch "{batch.name}" created. Now add employees via bulk upload or manual entry.', "success")
        return redirect(url_for("id_cards.batch_view", batch_id=batch.id))

    return render_template("id_cards/batch_form.html", batch=None)


@id_cards_bp.route("/batch/<int:batch_id>/edit", methods=["GET", "POST"])
@login_required
def batch_edit(batch_id):
    batch = get_owned_or_404(Batch, batch_id)
    if request.method == "POST":
        batch.name = request.form["name"].strip()
        batch.company_name = request.form["company_name"].strip()
        batch.company_address = request.form["company_address"].strip()
        batch.signature_label = request.form.get("signature_label", "Issuing Authority").strip() or "Issuing Authority"

        logo = request.files.get("logo")
        if logo and logo.filename and allowed_file(logo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            delete_if_exists(os.path.join(current_app.config["LOGO_DIR"], batch.logo_filename or ""))
            batch.logo_filename = save_upload(logo, current_app.config["LOGO_DIR"], prefix="logo_")

        signature = request.files.get("signature")
        if signature and signature.filename and allowed_file(signature.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            delete_if_exists(os.path.join(current_app.config["SIGNATURE_DIR"], batch.signature_filename or ""))
            batch.signature_filename = save_upload(signature, current_app.config["SIGNATURE_DIR"], prefix="sig_")

        db.session.commit()
        flash("Batch settings updated. Regenerate cards for changes (logo/address) to reflect on them.", "success")
        return redirect(url_for("id_cards.batch_view", batch_id=batch.id))

    return render_template("id_cards/batch_form.html", batch=batch)


@id_cards_bp.route("/batch/<int:batch_id>/delete", methods=["POST"])
@login_required
def batch_delete(batch_id):
    batch = get_owned_or_404(Batch, batch_id)
    delete_batch(batch)
    db.session.commit()
    flash("Batch and all its cards were deleted.", "info")
    return redirect(url_for("id_cards.batches"))


@id_cards_bp.route("/batch/<int:batch_id>")
@login_required
def batch_view(batch_id):
    batch = get_owned_or_404(Batch, batch_id)
    cards = IDCard.query.filter_by(batch_id=batch_id).order_by(IDCard.sr_no.asc(), IDCard.id.asc()).all()
    return render_template("id_cards/list.html", batch=batch, cards=cards)


# ---------------------------------------------------------------------
# Bulk upload
# ---------------------------------------------------------------------
@id_cards_bp.route("/batch/<int:batch_id>/bulk-upload", methods=["GET", "POST"])
@login_required
def bulk_upload(batch_id):
    batch = get_owned_or_404(Batch, batch_id)

    if request.method == "POST":
        data_file = request.files.get("data_file")
        if not data_file or not data_file.filename:
            flash("Please choose a CSV or Excel file to upload.", "error")
            return redirect(url_for("id_cards.bulk_upload", batch_id=batch.id))

        if not allowed_file(data_file.filename, current_app.config["ALLOWED_DATA_EXTENSIONS"]):
            flash("Only .csv, .xlsx or .xls files are supported.", "error")
            return redirect(url_for("id_cards.bulk_upload", batch_id=batch.id))

        tmp_dir = os.path.join(current_app.config["UPLOAD_ROOT"], "_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        safe_name = secure_filename(data_file.filename) or "upload"
        tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_{safe_name}")
        data_file.save(tmp_path)

        try:
            records = read_bulk_file(tmp_path)
        except Exception as exc:
            flash(f"Could not read file: {exc}", "error")
            return redirect(url_for("id_cards.bulk_upload", batch_id=batch.id))
        finally:
            delete_if_exists(tmp_path)

        if not records:
            flash("No valid rows found in the uploaded file.", "error")
            return redirect(url_for("id_cards.bulk_upload", batch_id=batch.id))

        existing_codes = {c.employee_code for c in batch.cards}
        added, skipped = 0, 0
        for rec in records:
            if rec["employee_code"] in existing_codes:
                skipped += 1
                continue
            card = IDCard(batch_id=batch.id, **rec, status="pending_photo")
            db.session.add(card)
            existing_codes.add(rec["employee_code"])
            added += 1

        db.session.commit()
        flash(f"Bulk upload complete: {added} employee(s) added, {skipped} skipped (duplicate employee code).",
              "success" if added else "warning")
        return redirect(url_for("id_cards.batch_view", batch_id=batch.id))

    return render_template("id_cards/bulk_upload.html", batch=batch)


# ---------------------------------------------------------------------
# Manual entry / edit
# ---------------------------------------------------------------------
def _card_form_fields(form):
    return {
        "name": form.get("name", "").strip(),
        "employee_code": form.get("employee_code", "").strip(),
        "designation": form.get("designation", "").strip(),
        "blood_group": form.get("blood_group", "").strip(),
        "landline": form.get("landline", "").strip(),
        "emergency_contact": form.get("emergency_contact", "").strip(),
        "employee_contact": form.get("employee_contact", "").strip(),
        "email": form.get("email", "").strip(),
    }


@id_cards_bp.route("/batch/<int:batch_id>/entry/new", methods=["GET", "POST"])
@login_required
def entry_new(batch_id):
    batch = get_owned_or_404(Batch, batch_id)

    if request.method == "POST":
        fields = _card_form_fields(request.form)
        if not fields["name"] or not fields["employee_code"]:
            flash("Name and Employee Code are required.", "error")
            return render_template("id_cards/entry_form.html", batch=batch, card=None, form=fields)

        if IDCard.query.filter_by(batch_id=batch.id, employee_code=fields["employee_code"]).first():
            flash("An employee with this code already exists in this batch.", "error")
            return render_template("id_cards/entry_form.html", batch=batch, card=None, form=fields)

        card = IDCard(batch_id=batch.id, **fields)

        photo = request.files.get("photo")
        if photo and photo.filename and allowed_file(photo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            card.photo_filename = save_upload(photo, current_app.config["PHOTO_DIR"], prefix="photo_")

        card.refresh_status()
        db.session.add(card)
        db.session.commit()
        flash(f"Employee {card.name} added.", "success")
        return redirect(url_for("id_cards.batch_view", batch_id=batch.id))

    return render_template("id_cards/entry_form.html", batch=batch, card=None, form=None)


@id_cards_bp.route("/card/<int:card_id>/edit", methods=["GET", "POST"])
@login_required
def card_edit(card_id):
    card = get_owned_card_or_404(card_id)
    batch = card.batch

    if request.method == "POST":
        fields = _card_form_fields(request.form)
        if not fields["name"] or not fields["employee_code"]:
            flash("Name and Employee Code are required.", "error")
            return render_template("id_cards/entry_form.html", batch=batch, card=card, form=fields)

        duplicate = IDCard.query.filter(
            IDCard.batch_id == batch.id,
            IDCard.employee_code == fields["employee_code"],
            IDCard.id != card.id,
        ).first()
        if duplicate:
            flash("Another employee in this batch already uses this code.", "error")
            return render_template("id_cards/entry_form.html", batch=batch, card=card, form=fields)

        for key, value in fields.items():
            setattr(card, key, value)

        photo = request.files.get("photo")
        if photo and photo.filename and allowed_file(photo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            delete_if_exists(os.path.join(current_app.config["PHOTO_DIR"], card.photo_filename or ""))
            card.photo_filename = save_upload(photo, current_app.config["PHOTO_DIR"], prefix="photo_")

        card.refresh_status()
        db.session.commit()
        flash("Employee details updated. Regenerate the card to apply changes to the printed card/QR.", "success")
        return redirect(url_for("id_cards.batch_view", batch_id=batch.id))

    return render_template("id_cards/entry_form.html", batch=batch, card=card, form=None)


@id_cards_bp.route("/card/<int:card_id>/photo", methods=["POST"])
@login_required
def card_photo_upload(card_id):
    """Quick inline photo upload from the list view (used for bulk-then-photo workflow)."""
    card = get_owned_card_or_404(card_id)
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        flash("No photo selected.", "error")
        return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))

    if not allowed_file(photo.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
        flash("Photo must be a PNG, JPG or WEBP file.", "error")
        return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))

    delete_if_exists(os.path.join(current_app.config["PHOTO_DIR"], card.photo_filename or ""))
    card.photo_filename = save_upload(photo, current_app.config["PHOTO_DIR"], prefix="photo_")
    card.refresh_status()
    db.session.commit()
    flash(f"Photo uploaded for {card.name}. You can now generate the card.", "success")
    return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))


@id_cards_bp.route("/card/<int:card_id>/delete", methods=["POST"])
@login_required
def card_delete(card_id):
    card = get_owned_card_or_404(card_id)
    batch_id = card.batch_id
    remove_card_files(card)
    db.session.delete(card)
    db.session.commit()
    flash("Employee record deleted.", "info")
    return redirect(url_for("id_cards.batch_view", batch_id=batch_id))


# ---------------------------------------------------------------------
# Generate / Regenerate
# ---------------------------------------------------------------------
def _generate_single_card(card: IDCard) -> bool:
    """Render the card image + QR for one employee. Returns True on success."""
    if not card.photo_filename:
        return False

    batch = card.batch
    photo_path = os.path.join(current_app.config["PHOTO_DIR"], card.photo_filename)
    logo_path = os.path.join(current_app.config["LOGO_DIR"], batch.logo_filename) if batch.logo_filename else None
    signature_path = os.path.join(current_app.config["SIGNATURE_DIR"], batch.signature_filename) if batch.signature_filename else None

    # Clean up previous artefacts before regenerating
    delete_if_exists(os.path.join(current_app.config["ID_CARD_DIR"], card.card_filename or ""))
    delete_if_exists(os.path.join(current_app.config["QR_DIR"], card.qr_filename or ""))

    card_filename, footer_top = render_id_card(
        company_name=batch.company_name,
        company_address=batch.company_address,
        logo_path=logo_path,
        signature_path=signature_path,
        signature_label=batch.signature_label or "Issuing Authority",
        photo_path=photo_path,
        name=card.name,
        employee_code=card.employee_code,
        blood_group=card.blood_group,
        employee_contact=card.employee_contact,
        emergency_contact=card.emergency_contact,
        landline=card.landline,
        destination_dir=current_app.config["ID_CARD_DIR"],
    )

    view_url = public_url_for("id_cards.view_card_public", card_id=card.id)
    qr_filename, target_url, short_url = save_qr_for_url(
        view_url, current_app.config["QR_DIR"], filename_prefix=f"qr_{card.employee_code}"
    )

    card_full_path = os.path.join(current_app.config["ID_CARD_DIR"], card_filename)
    qr_full_path = os.path.join(current_app.config["QR_DIR"], qr_filename)
    paste_qr_on_card(card_full_path, qr_full_path, footer_top)

    card.card_filename = card_filename
    card.qr_filename = qr_filename
    card.qr_target_url = target_url
    card.qr_short_url = short_url
    card.refresh_status()
    return True


@id_cards_bp.route("/card/<int:card_id>/generate", methods=["POST"])
@login_required
def card_generate(card_id):
    card = get_owned_card_or_404(card_id)
    is_new = card.status != "generated"

    # Regenerating an existing card is free; a first-time card uses quota.
    if is_new and card.photo_filename:
        status = quota_status(g.user, "id_cards")
        if status["at_limit"]:
            flash(limit_message(status), "error")
            return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))

    if _generate_single_card(card):
        if is_new:
            record_usage(g.user, "id_cards")
        db.session.commit()
        flash(f"Card {'generated' if is_new else 'regenerated'} for {card.name}.", "success")
    else:
        flash("Upload a photo before generating the card.", "error")
    return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))


@id_cards_bp.route("/batch/<int:batch_id>/generate-all", methods=["POST"])
@login_required
def batch_generate_all(batch_id):
    batch = get_owned_or_404(Batch, batch_id)
    status = quota_status(g.user, "id_cards")
    allowance = status["remaining"]          # None = unlimited

    regenerated, created, no_photo, over_limit = 0, 0, 0, 0
    for card in batch.cards:
        if not card.photo_filename:
            no_photo += 1
            continue
        is_new = card.status != "generated"
        if is_new and allowance is not None and created >= allowance:
            over_limit += 1
            continue
        if _generate_single_card(card):
            if is_new:
                created += 1
            else:
                regenerated += 1
    if created:
        record_usage(g.user, "id_cards", created)
    db.session.commit()

    parts = []
    if created:
        parts.append(f"{created} new card{'' if created == 1 else 's'} generated")
    if regenerated:
        parts.append(f"{regenerated} regenerated")
    if no_photo:
        parts.append(f"{no_photo} still need a photo")
    message = (", ".join(parts) or "Nothing to generate") + "."
    if over_limit:
        message += (f" {over_limit} card{'' if over_limit == 1 else 's'} skipped because you've "
                    "reached your limit — ask your administrator for a higher limit.")
    flash(message, "warning" if (over_limit or not (created or regenerated)) else "success")
    return redirect(url_for("id_cards.batch_view", batch_id=batch_id))


# ---------------------------------------------------------------------
# Public verification view (this is the URL embedded in the card's QR)
# ---------------------------------------------------------------------
@id_cards_bp.route("/verify/<int:card_id>")
def view_card_public(card_id):
    # Public on purpose: this is what the printed card's QR opens, so it
    # must work for anyone, signed in or not. Existing printed cards use
    # this exact URL, so it never changes.
    card = IDCard.query.get_or_404(card_id)
    return render_template("id_cards/card_view.html", card=card, batch=card.batch)


@id_cards_bp.route("/download/qr/<int:card_id>")
@login_required
def download_qr(card_id):
    """Download just the verification QR PNG for one employee."""
    card = get_owned_card_or_404(card_id)
    if not card.qr_filename:
        flash("This card hasn't been generated yet, so there's no QR code to download.", "error")
        return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))
    return send_from_directory(
        current_app.config["QR_DIR"],
        card.qr_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(card.employee_code)}-{safe_download_name(card.name)}-qr.png",
    )


@id_cards_bp.route("/download/card/<int:card_id>")
@login_required
def download_card(card_id):
    card = get_owned_card_or_404(card_id)
    if not card.card_filename:
        flash("This card hasn't been generated yet.", "error")
        return redirect(url_for("id_cards.batch_view", batch_id=card.batch_id))
    return send_from_directory(
        current_app.config["ID_CARD_DIR"],
        card.card_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(card.employee_code)}-{safe_download_name(card.name)}-id-card.png",
    )