import os
import re
from datetime import datetime

from flask import (Blueprint, Response, current_app, flash, redirect,
                   render_template, request, send_from_directory, url_for)

from extensions import db
from models import Invitation
from utils.decorators import login_required
from utils.url_helpers import public_url_for
from utils.event_types import EVENT_TYPES, event_meta, grouped_events
from utils.file_helpers import (allowed_file, delete_if_exists,
                                safe_download_name, save_upload)
from utils.invite_utils import build_ics, google_calendar_url, validate_location
from utils.qr_utils import save_qr_for_url
from utils.vcard_utils import unique_slug

invitation_bp = Blueprint("invitation", __name__, url_prefix="/invitation")

HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _clean_color(value, default):
    value = (value or "").strip()
    return value if HEX_COLOR.match(value) else default


def _parse_dt(date_value: str, time_value: str, default_time: str = None):
    """
    Combine the separate date and time inputs into one datetime.

    A blank time returns None unless `default_time` is given — an omitted
    end time means "no end time", not midnight, which would otherwise read
    as ending before the event starts.
    """
    date_value = (date_value or "").strip()
    time_value = (time_value or "").strip() or default_time
    if not date_value or not time_value:
        return None
    try:
        return datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _form_context(invitation, form, mode):
    return {
        "invitation": invitation,
        "form": form,
        "mode": mode,
        "event_types": EVENT_TYPES,
        "grouped": grouped_events(),
    }


def _apply(invitation, form, files, is_new):
    """
    Copy the submitted form onto the invitation.

    Returns an error string on the first validation failure, or None when
    everything applied cleanly.
    """
    event_type = form.get("event_type", "").strip()
    if event_type not in EVENT_TYPES:
        return "Pick an event type to continue."
    invitation.event_type = event_type
    meta = event_meta(event_type)

    # ---- Host details, per the event type's own field list ----
    details = {}
    for field_name, label, required, _placeholder in meta["hosts"]:
        value = form.get(f"host_{field_name}", "").strip()
        if required and not value:
            return f"{label} is required for a {meta['name'].lower()}."
        if value:
            details[field_name] = value[:200]
    invitation.set_host_details(details)

    invitation.title = (form.get("title", "").strip() or meta["name"])[:200]

    # ---- Session 1 ----
    primary_start = _parse_dt(form.get("primary_date"), form.get("primary_time"), "00:00")
    if not primary_start:
        return "Enter the event date and time."
    invitation.primary_start = primary_start
    invitation.primary_end = _parse_dt(form.get("primary_date"), form.get("primary_end_time"))
    if invitation.primary_end and invitation.primary_end <= primary_start:
        return "The end time must be after the start time."
    invitation.primary_label = (
        form.get("primary_label", "").strip()
        or (meta.get("session_labels", ("Ceremony",))[0] if meta["two_sessions"] else "Ceremony")
    )[:120]

    # ---- Session 2 (weddings) ----
    if meta["two_sessions"]:
        secondary_start = _parse_dt(form.get("secondary_date"), form.get("secondary_time"), "00:00")
        if not secondary_start:
            return "A wedding needs both a ceremony and a reception date and time."
        invitation.secondary_start = secondary_start
        invitation.secondary_end = _parse_dt(
            form.get("secondary_date"), form.get("secondary_end_time")
        )
        if invitation.secondary_end and invitation.secondary_end <= secondary_start:
            return "The reception end time must be after its start time."
        invitation.secondary_label = (
            form.get("secondary_label", "").strip() or meta["session_labels"][1]
        )[:120]
    else:
        invitation.secondary_start = None
        invitation.secondary_end = None
        invitation.secondary_label = None

    # ---- Venue ----
    venue_name = form.get("venue_name", "").strip()
    if not venue_name:
        return "Enter the venue name — guests need to know where to go."
    invitation.venue_name = venue_name[:200]
    invitation.venue_address = form.get("venue_address", "").strip()[:500] or None

    ok, lat, lng, map_url, error = validate_location(form.get("location_ref"))
    if not ok:
        return error
    invitation.latitude = lat
    invitation.longitude = lng
    invitation.map_url = map_url

    # ---- Content ----
    invitation.message = form.get("message", "").strip() or None
    invitation.rsvp_phone = form.get("rsvp_phone", "").strip()[:30] or None
    invitation.rsvp_whatsapp = form.get("rsvp_whatsapp", "").strip()[:30] or None
    invitation.dress_code = form.get("dress_code", "").strip()[:150] or None

    invitation.primary_color = _clean_color(form.get("primary_color"), meta["palette"][0])
    invitation.secondary_color = _clean_color(form.get("secondary_color"), meta["palette"][1])

    # ---- Hero image ----
    hero = files.get("hero")
    if hero and hero.filename:
        if not allowed_file(hero.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            return "The photo must be a PNG, JPG, JPEG or WEBP file."
        if invitation.hero_filename:
            delete_if_exists(
                os.path.join(current_app.config["INVITE_IMAGE_DIR"], invitation.hero_filename)
            )
        invitation.hero_filename = save_upload(
            hero, current_app.config["INVITE_IMAGE_DIR"], prefix="inv_"
        )
    if form.get("remove_hero") == "on" and invitation.hero_filename:
        delete_if_exists(
            os.path.join(current_app.config["INVITE_IMAGE_DIR"], invitation.hero_filename)
        )
        invitation.hero_filename = None

    if is_new:
        invitation.slug = unique_slug(
            form.get("slug") or invitation.headline or meta["name"],
            lambda s: Invitation.query.filter_by(slug=s).first() is not None,
        )
    return None


def _regenerate_qr(invitation):
    if invitation.qr_filename:
        delete_if_exists(os.path.join(current_app.config["QR_DIR"], invitation.qr_filename))
    page_url = public_url_for("invitation.public_view", slug=invitation.slug)
    qr_filename, target_url, short_url = save_qr_for_url(
        page_url, current_app.config["QR_DIR"], filename_prefix="invite"
    )
    invitation.qr_filename = qr_filename
    invitation.qr_target_url = target_url
    invitation.qr_short_url = short_url


# ---------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------
@invitation_bp.route("/")
@login_required
def list_view():
    invitations = Invitation.query.order_by(Invitation.primary_start.desc()).all()
    return render_template("invitation/list.html", invitations=invitations)


@invitation_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        invitation = Invitation()
        error = _apply(invitation, request.form, request.files, is_new=True)
        if error:
            flash(error, "error")
            return render_template(
                "invitation/form.html", **_form_context(None, request.form, "create")
            )

        db.session.add(invitation)
        db.session.flush()
        _regenerate_qr(invitation)
        db.session.commit()

        flash(f"Invitation created for {invitation.headline}.", "success")
        return redirect(url_for("invitation.list_view"))

    return render_template("invitation/form.html", **_form_context(None, None, "create"))


@invitation_bp.route("/<int:invitation_id>/edit", methods=["GET", "POST"])
@login_required
def edit(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)

    if request.method == "POST":
        error = _apply(invitation, request.form, request.files, is_new=False)
        if error:
            db.session.rollback()
            flash(error, "error")
            return render_template(
                "invitation/form.html", **_form_context(invitation, request.form, "edit")
            )
        db.session.commit()
        flash("Invitation updated. The shared link and QR are unchanged.", "success")
        return redirect(url_for("invitation.list_view"))

    return render_template("invitation/form.html", **_form_context(invitation, None, "edit"))


@invitation_bp.route("/<int:invitation_id>/regenerate", methods=["POST"])
@login_required
def regenerate(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    _regenerate_qr(invitation)
    db.session.commit()
    flash("QR code regenerated.", "success")
    return redirect(url_for("invitation.list_view"))


@invitation_bp.route("/<int:invitation_id>/delete", methods=["POST"])
@login_required
def delete(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.hero_filename:
        delete_if_exists(
            os.path.join(current_app.config["INVITE_IMAGE_DIR"], invitation.hero_filename)
        )
    if invitation.qr_filename:
        delete_if_exists(os.path.join(current_app.config["QR_DIR"], invitation.qr_filename))
    db.session.delete(invitation)
    db.session.commit()
    flash("Invitation deleted. Its page and QR no longer resolve.", "info")
    return redirect(url_for("invitation.list_view"))


@invitation_bp.route("/<int:invitation_id>/qr")
@login_required
def download_qr(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if not invitation.qr_filename:
        flash("This invitation has no QR code yet — regenerate it first.", "error")
        return redirect(url_for("invitation.list_view"))
    return send_from_directory(
        current_app.config["QR_DIR"],
        invitation.qr_filename,
        as_attachment=True,
        download_name=f"{safe_download_name(invitation.headline)}-invite-qr.png",
    )


@invitation_bp.route("/preview/<int:invitation_id>")
@login_required
def preview(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    return render_template(
        "invitation/public.html",
        inv=invitation,
        is_preview=True,
        gcal=lambda s: google_calendar_url(invitation, s),
    )


# ---------------------------------------------------------------------
# Public views — what the QR opens
# ---------------------------------------------------------------------
@invitation_bp.route("/image/<path:filename>")
def serve_image(filename):
    return send_from_directory(current_app.config["INVITE_IMAGE_DIR"], filename)


@invitation_bp.route("/i/<slug>")
def public_view(slug):
    invitation = Invitation.query.filter_by(slug=slug).first_or_404()
    page_url = public_url_for("invitation.public_view", slug=slug)
    return render_template(
        "invitation/public.html",
        inv=invitation,
        is_preview=False,
        gcal=lambda s: google_calendar_url(invitation, s, page_url),
    )


@invitation_bp.route("/i/<slug>/event.ics")
def calendar_file(slug):
    """
    The 'Add to calendar' action.

    Served as text/calendar with a filename so iOS opens it in the Calendar
    app's add-event sheet and Android hands it to the calendar handler.
    """
    invitation = Invitation.query.filter_by(slug=slug).first_or_404()
    page_url = public_url_for("invitation.public_view", slug=slug)
    payload = build_ics(invitation, page_url=page_url)
    filename = f"{safe_download_name(invitation.headline, 'invitation')}.ics"
    return Response(
        payload.encode("utf-8"),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )