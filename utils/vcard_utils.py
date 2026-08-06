"""
Helpers for the vCard module: URL slugs, the downloadable .vcf contact
file, and the social platform catalogue used by the form and the public
page.
"""

import re
import uuid

# Platform key -> (display name, brand colour, monogram)
# Monograms are used instead of brand logo artwork so nothing here depends
# on shipping third-party trademarks with the app.
SOCIAL_PLATFORMS = {
    "website": ("Website", "#1e5ba8", "W"),
    "instagram": ("Instagram", "#d62976", "IG"),
    "facebook": ("Facebook", "#1877f2", "F"),
    "linkedin": ("LinkedIn", "#0a66c2", "in"),
    "x": ("X", "#111111", "X"),
    "youtube": ("YouTube", "#ff0000", "YT"),
    "whatsapp": ("WhatsApp", "#25d366", "WA"),
    "telegram": ("Telegram", "#229ed9", "TG"),
    "github": ("GitHub", "#24292f", "GH"),
    "pinterest": ("Pinterest", "#bd081c", "P"),
    "snapchat": ("Snapchat", "#c9b000", "SC"),
    "tiktok": ("TikTok", "#010101", "TT"),
    "google": ("Google Business", "#ea4335", "G"),
    "skype": ("Skype", "#00aff0", "S"),
    "reddit": ("Reddit", "#ff4500", "R"),
    "tripadvisor": ("Tripadvisor", "#00af87", "TA"),
    "vimeo": ("Vimeo", "#1ab7ea", "V"),
    "dribbble": ("Dribbble", "#ea4c89", "D"),
}


def platform_meta(key: str):
    """Return (name, colour, monogram) for a platform key, with a safe default."""
    return SOCIAL_PLATFORMS.get((key or "").lower(), ("Link", "#5a687a", "L"))


def slugify(value: str, fallback: str = "card") -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (value or "")).strip("-").lower()
    return (slug or fallback)[:50]


def unique_slug(base: str, exists) -> str:
    """
    Build a slug that isn't taken yet.

    `exists` is a callable receiving a candidate slug and returning True if
    it is already in use — the caller supplies the DB lookup so this module
    stays free of query code.
    """
    root = slugify(base)
    candidate = root
    while exists(candidate):
        candidate = f"{root}-{uuid.uuid4().hex[:5]}"
    return candidate


def _escape(text: str) -> str:
    """Escape per RFC 6350: backslash, comma, semicolon and newlines."""
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def build_vcf(card, photo_url: str = "", page_url: str = "") -> str:
    """
    Build a vCard 3.0 payload for the "Add contact" button.

    3.0 rather than 4.0 because iOS and Android contact importers handle it
    most consistently; 4.0 still trips up some older Android builds.
    """
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_escape(card.last_name)};{_escape(card.first_name)};;;",
        f"FN:{_escape(card.full_name)}",
    ]

    if card.company:
        lines.append(f"ORG:{_escape(card.company)}")
    if card.profession:
        lines.append(f"TITLE:{_escape(card.profession)}")

    for link in card.phones:
        kind = _escape(link.label or "CELL").upper()[:20]
        lines.append(f"TEL;TYPE={kind}:{_escape(link.value)}")

    for link in card.emails:
        kind = _escape(link.label or "WORK").upper()[:20]
        lines.append(f"EMAIL;TYPE={kind}:{_escape(link.value)}")

    for link in card.websites:
        lines.append(f"URL:{_escape(link.value)}")
    for link in card.socials:
        lines.append(f"URL:{_escape(link.value)}")

    if card.formatted_address:
        lines.append(
            "ADR;TYPE=WORK:;;{};{};{};{};{}".format(
                _escape(card.address_line),
                _escape(card.city),
                _escape(card.state),
                _escape(card.postal_code),
                _escape(card.country),
            )
        )

    if card.summary:
        lines.append(f"NOTE:{_escape(card.summary)}")
    if photo_url:
        lines.append(f"PHOTO;VALUE=URI:{photo_url}")
    if page_url:
        lines.append(f"URL;TYPE=PROFILE:{page_url}")

    lines.append("END:VCARD")
    # CRLF line endings — some contact importers reject bare LF.
    return "\r\n".join(lines) + "\r\n"