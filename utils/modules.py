"""
The six portal modules, described once.

Blueprint names match the module keys, so a request's blueprint tells us
which module it belongs to. Everything that needs a list of modules — the
sidebar, the dashboard, the admin access grid, quota checks — reads from
here, so they can never drift apart.
"""

from collections import OrderedDict

MODULES = OrderedDict([
    ("id_cards", {
        "label": "ID Card Generator",
        "short": "ID Cards",
        "icon": "&#127915;",
        "endpoint": "id_cards.batches",
        "unit": "cards generated",
        "unit_one": "card generated",
        "blurb": "Batch employee ID cards with a verification QR.",
    }),
    ("vcard", {
        "label": "Digital vCards",
        "short": "vCards",
        "icon": "&#128100;",
        "endpoint": "vcard.list_view",
        "unit": "vCards",
        "unit_one": "vCard",
        "blurb": "Shareable contact pages with an Add-contact button.",
    }),
    ("invitation", {
        "label": "Invitations",
        "short": "Invitations",
        "icon": "&#128233;",
        "endpoint": "invitation.list_view",
        "unit": "invitations",
        "unit_one": "invitation",
        "blurb": "Event cards guests can save to their calendar.",
    }),
    ("url_qr", {
        "label": "URL QR",
        "short": "URL QR",
        "icon": "&#128279;",
        "endpoint": "url_qr.list_view",
        "unit": "URL QR codes",
        "unit_one": "URL QR code",
        "blurb": "A scannable code for any web address.",
    }),
    ("image_qr", {
        "label": "Image QR",
        "short": "Image QR",
        "icon": "&#128247;",
        "endpoint": "image_qr.list_view",
        "unit": "image QR codes",
        "unit_one": "image QR code",
        "blurb": "Upload an image, get a code that opens it.",
    }),
    ("upi_qr", {
        "label": "UPI Payment QR",
        "short": "UPI QR",
        "icon": "&#8377;",
        "endpoint": "upi_qr.list_view",
        "unit": "UPI QR codes",
        "unit_one": "UPI QR code",
        "blurb": "Payment codes for any UPI app.",
    }),
])

MODULE_KEYS = tuple(MODULES.keys())

# Starting point if default_permissions has no row for a module yet
# (fresh install without the migration seed). Matches the SQL seed.
FALLBACK_DEFAULT_QUOTA = {
    "id_cards": 25, "vcard": 10, "invitation": 10,
    "url_qr": 10, "image_qr": 10, "upi_qr": 10,
}

# Endpoints that are reachable without signing in — these are what a
# scanned QR code opens. Everything else in a module blueprint requires
# a signed-in owner.
PUBLIC_ENDPOINTS = frozenset({
    "id_cards.view_card_public",
    "image_qr.serve_image",
    "vcard.serve_image",
    "vcard.public_view",
    "vcard.contact_vcf",
    "invitation.serve_image",
    "invitation.public_view",
    "invitation.calendar_file",
})

# GET pages that only make sense when the module is switched on
# (forms that lead to creating or changing something). When an admin turns
# a module off, the user keeps read-only access to what they already made.
WRITE_FORM_ENDPOINTS = frozenset({
    "id_cards.batch_new", "id_cards.batch_edit", "id_cards.bulk_upload",
    "id_cards.entry_new", "id_cards.card_edit",
    "vcard.create", "vcard.edit",
    "invitation.create", "invitation.edit",
    "url_qr.create", "url_qr.edit",
    "image_qr.upload",
    "upi_qr.generate",
})


def module_meta(key: str) -> dict:
    return MODULES.get(key, {})
