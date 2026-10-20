"""
Delete records together with the files they own on disk.

Used by the per-module delete actions and by "delete user" in the admin
area, so a removed record never leaves orphaned photos or QR images.
"""

import os

from flask import current_app

from extensions import db
from models import Batch, ImageQR, Invitation, UpiQR, UrlQR, VCard
from utils.file_helpers import delete_if_exists


def _rm(folder_key: str, filename):
    if filename:
        delete_if_exists(os.path.join(current_app.config[folder_key], filename))


def remove_card_files(card):
    _rm("PHOTO_DIR", card.photo_filename)
    _rm("ID_CARD_DIR", card.card_filename)
    _rm("QR_DIR", card.qr_filename)


def delete_batch(batch: Batch):
    for card in batch.cards:
        remove_card_files(card)
    _rm("LOGO_DIR", batch.logo_filename)
    _rm("SIGNATURE_DIR", batch.signature_filename)
    db.session.delete(batch)


def delete_vcard(card: VCard):
    _rm("VCARD_IMAGE_DIR", card.image_filename)
    _rm("QR_DIR", card.qr_filename)
    db.session.delete(card)


def delete_invitation(invitation: Invitation):
    _rm("INVITE_IMAGE_DIR", invitation.hero_filename)
    _rm("QR_DIR", invitation.qr_filename)
    db.session.delete(invitation)


def delete_url_qr(item: UrlQR):
    _rm("QR_DIR", item.qr_filename)
    db.session.delete(item)


def delete_image_qr(item: ImageQR):
    _rm("IMAGE_QR_SOURCE_DIR", item.image_filename)
    _rm("QR_DIR", item.qr_filename)
    db.session.delete(item)


def delete_upi_qr(item: UpiQR):
    _rm("QR_DIR", item.qr_filename)
    db.session.delete(item)


def delete_everything_owned_by(user) -> int:
    """Remove all of a user's records and files. Returns how many top-level records went."""
    removed = 0
    for model, fn in (
        (Batch, delete_batch), (VCard, delete_vcard), (Invitation, delete_invitation),
        (UrlQR, delete_url_qr), (ImageQR, delete_image_qr), (UpiQR, delete_upi_qr),
    ):
        for item in model.query.filter(model.owner_id == user.id).all():
            fn(item)
            removed += 1
    return removed
