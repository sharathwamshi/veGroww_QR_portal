import json
from datetime import datetime, timedelta

from extensions import db
from utils.event_types import event_meta


class Invitation(db.Model):
    """
    A digital invitation card.

    Host details vary by event type (bride/groom for a wedding, baby name for
    a naming ceremony), so rather than a column per field they're stored as
    JSON in `host_details` and described by utils/event_types.py. That way a
    new event type needs no migration.

    Sessions: every event has a primary date/time. Weddings additionally have
    a second session (reception), driven by the event type's `two_sessions`
    flag.
    """

    __tablename__ = "invitations"

    id = db.Column(db.Integer, primary_key=True)

    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    # Host names etc., keyed by the field names in event_types.py
    host_details_json = db.Column(db.Text, nullable=True)

    # ---- Session 1 (always present) ----
    primary_label = db.Column(db.String(120))
    primary_start = db.Column(db.DateTime, nullable=False)
    primary_end = db.Column(db.DateTime)

    # ---- Session 2 (weddings: the reception) ----
    secondary_label = db.Column(db.String(120))
    secondary_start = db.Column(db.DateTime)
    secondary_end = db.Column(db.DateTime)

    # ---- Venue ----
    venue_name = db.Column(db.String(200), nullable=False)
    venue_address = db.Column(db.String(500))
    map_url = db.Column(db.String(700))          # Google Maps / Apple Maps link
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # ---- Content ----
    message = db.Column(db.Text)                 # note to guests
    rsvp_phone = db.Column(db.String(30))
    rsvp_whatsapp = db.Column(db.String(30))
    dress_code = db.Column(db.String(150))
    hero_filename = db.Column(db.String(255))    # optional photo

    # ---- Design ----
    primary_color = db.Column(db.String(7), nullable=False, default="#8C1D40")
    secondary_color = db.Column(db.String(7), nullable=False, default="#D4A15E")

    # ---- QR ----
    qr_filename = db.Column(db.String(255))
    qr_target_url = db.Column(db.String(500))
    qr_short_url = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ------------------------------------------------------------------
    # Derived values used by the templates
    # ------------------------------------------------------------------
    @property
    def meta(self) -> dict:
        return event_meta(self.event_type)

    @property
    def host_details(self) -> dict:
        if not self.host_details_json:
            return {}
        try:
            return json.loads(self.host_details_json)
        except (ValueError, TypeError):
            return {}

    def set_host_details(self, mapping: dict):
        cleaned = {k: v for k, v in (mapping or {}).items() if v}
        self.host_details_json = json.dumps(cleaned, ensure_ascii=False) if cleaned else None

    def host(self, field: str, default: str = "") -> str:
        return self.host_details.get(field, default)

    @property
    def headline(self) -> str:
        """
        The big names on the card — a couple for weddings, otherwise
        whichever single celebrant the event type collects.
        """
        details = self.host_details
        bride, groom = details.get("bride_name"), details.get("groom_name")
        if bride and groom:
            return f"{bride} & {groom}"
        for key in ("couple_names", "baby_name", "celebrant_name",
                    "remembered_name", "business_name", "family_name"):
            if details.get(key):
                return details[key]
        return self.title

    @property
    def sessions(self):
        """Both sessions as a uniform list, so templates don't branch."""
        out = [{
            "label": self.primary_label or "Ceremony",
            "start": self.primary_start,
            "end": self.primary_end,
        }]
        if self.secondary_start:
            out.append({
                "label": self.secondary_label or "Reception",
                "start": self.secondary_start,
                "end": self.secondary_end,
            })
        return out

    @property
    def has_map(self) -> bool:
        return bool(self.map_url or (self.latitude is not None and self.longitude is not None))

    @property
    def maps_link(self) -> str:
        """A link that opens the venue in the phone's map app."""
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
        return self.map_url or ""

    @property
    def geo_uri(self) -> str:
        """geo: scheme — Android offers the user's preferred map app."""
        if self.latitude is not None and self.longitude is not None:
            return f"geo:{self.latitude},{self.longitude}"
        return ""

    @property
    def is_past(self) -> bool:
        last = self.secondary_start or self.primary_start
        return bool(last and last < datetime.utcnow() - timedelta(hours=12))

    def __repr__(self):
        return f"<Invitation {self.slug} ({self.event_type})>"
