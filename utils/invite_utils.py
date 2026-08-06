"""
Calendar (.ics) and map-location helpers for the invitation module.

Calendar strategy: the invitation page offers a downloadable .ics file.
iOS opens it directly in the Calendar app's "Add event" sheet; Android
hands it to Google Calendar (or whichever calendar app is registered).
A Google Calendar web link is also offered as a fallback for desktop
browsers and any Android device without a handler for text/calendar.

All times are written as floating local times (no timezone suffix), which
is the correct reading for an invitation: an 11:00 muhurtham is 11:00
where the event happens, regardless of the guest's phone timezone.
"""

import re
from datetime import datetime, timedelta
from urllib.parse import quote

# Accepts the forms people actually paste from a phone:
#   https://maps.app.goo.gl/xxxx           (share sheet short link)
#   https://goo.gl/maps/xxxx               (legacy short link)
#   https://www.google.com/maps/...        (desktop link)
#   https://maps.google.com/...
#   https://maps.apple.com/?ll=...
GOOGLE_MAPS_HOSTS = re.compile(
    r"^https?://("
    r"maps\.app\.goo\.gl|"
    r"goo\.gl/maps|"
    r"(www\.)?google\.[a-z.]{2,6}/maps|"
    r"maps\.google\.[a-z.]{2,6}|"
    r"maps\.apple\.com"
    r")/?",
    re.IGNORECASE,
)

# "12.9716, 77.5946" or "12.9716,77.5946" — what you get from
# "Copy coordinates" in Google Maps.
COORD_PATTERN = re.compile(
    r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$"
)


def parse_coordinates(text: str):
    """
    Pull (lat, lng) out of a pasted string.

    Handles bare coordinate pairs, and coordinates embedded in a Google
    Maps URL (@lat,lng or ?q=lat,lng). Returns None when nothing valid is
    found — short share links don't contain coordinates and can only be
    resolved by following them, so those are stored as a plain link.
    """
    if not text:
        return None
    text = text.strip()

    match = COORD_PATTERN.match(text)
    if not match:
        # @12.97,77.59 in a /maps/place/... URL, or q=/query=/ll= parameters
        match = re.search(r"@(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)", text)
    if not match:
        match = re.search(
            r"[?&](?:q|query|ll|daddr)=(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)", text
        )
    if not match:
        return None

    try:
        lat, lng = float(match.group(1)), float(match.group(2))
    except (TypeError, ValueError):
        return None

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def is_map_link(text: str) -> bool:
    return bool(text) and bool(GOOGLE_MAPS_HOSTS.match(text.strip()))


def validate_location(raw: str):
    """
    Validate whatever the user pasted into the location field.

    Returns (ok, latitude, longitude, map_url, error_message).
    Coordinates win when present, since they let the page offer a `geo:`
    link that opens the phone's default map app rather than forcing the
    browser through Google.
    """
    raw = (raw or "").strip()
    if not raw:
        return True, None, None, None, None

    coords = parse_coordinates(raw)
    if coords:
        lat, lng = coords
        return True, lat, lng, f"https://www.google.com/maps/search/?api=1&query={lat},{lng}", None

    if is_map_link(raw):
        return True, None, None, raw[:700], None

    return (
        False, None, None, None,
        "Paste a Google or Apple Maps link, or coordinates like 12.9716, 77.5946. "
        "In Google Maps use Share to copy the link, or long-press the pin and tap "
        "the coordinates to copy them.",
    )


# ---------------------------------------------------------------------
# .ics generation
# ---------------------------------------------------------------------
def _ics_escape(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """
    RFC 5545 caps lines at 75 octets; continuations start with a space.

    The limit is in octets, not characters, so this measures encoded
    length — otherwise a name in Kannada or Hindi could overflow the
    line or get split mid-character.
    """
    if len(line.encode("utf-8")) <= 73:
        return line

    out, current, width = [], "", 0
    limit = 73
    for char in line:
        size = len(char.encode("utf-8"))
        if width + size > limit:
            out.append(current)
            current, width, limit = " ", 1, 72
        current += char
        width += size
    if current.strip():
        out.append(current)
    return "\r\n".join(out)


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def build_ics(invitation, page_url: str = "") -> str:
    """
    Build a calendar file containing one VEVENT per session, so a wedding
    adds both the ceremony and the reception in a single tap.
    """
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    location = ", ".join(
        part for part in (invitation.venue_name, invitation.venue_address) if part
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Vegroww QR Portal//Invitation//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for index, session in enumerate(invitation.sessions, start=1):
        start = session["start"]
        end = session["end"] or (start + timedelta(hours=3))
        summary = f"{invitation.headline} - {session['label']}"

        description_parts = [invitation.title]
        if invitation.message:
            description_parts.append(invitation.message)
        if invitation.dress_code:
            description_parts.append(f"Dress code: {invitation.dress_code}")
        if page_url:
            description_parts.append(page_url)

        lines += [
            "BEGIN:VEVENT",
            f"UID:invitation-{invitation.id}-{index}@vegroww-qr-portal",
            f"DTSTAMP:{now}",
            f"DTSTART:{_stamp(start)}",
            f"DTEND:{_stamp(end)}",
            _fold(f"SUMMARY:{_ics_escape(summary)}"),
            _fold(f"LOCATION:{_ics_escape(location)}"),
            _fold(f"DESCRIPTION:{_ics_escape(chr(10).join(description_parts))}"),
        ]
        if page_url:
            lines.append(_fold(f"URL:{page_url}"))
        if invitation.latitude is not None and invitation.longitude is not None:
            lines.append(f"GEO:{invitation.latitude};{invitation.longitude}")

        # A day-before reminder, which is what guests actually want.
        lines += [
            "STATUS:CONFIRMED",
            "BEGIN:VALARM",
            "TRIGGER:-P1D",
            "ACTION:DISPLAY",
            _fold(f"DESCRIPTION:{_ics_escape(summary)} is tomorrow"),
            "END:VALARM",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def google_calendar_url(invitation, session, page_url: str = "") -> str:
    """Web fallback — 'Add to Google Calendar' for desktop browsers."""
    start = session["start"]
    end = session["end"] or (start + timedelta(hours=3))
    details = invitation.message or invitation.title
    if page_url:
        details = f"{details}\n{page_url}"
    location = ", ".join(
        part for part in (invitation.venue_name, invitation.venue_address) if part
    )
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(invitation.headline + ' - ' + session['label'])}"
        f"&dates={_stamp(start)}/{_stamp(end)}"
        f"&details={quote(details)}"
        f"&location={quote(location)}"
    )
