from datetime import datetime

from extensions import db


class VCard(db.Model):
    """
    A digital business card. One row drives both the public landing page
    (/v/<slug>) and the QR code that opens it.

    Repeatable entries — phones, emails, websites, social links — live in
    VCardLink rather than fixed columns, so a card can carry as many of
    each as it needs and they keep the display order the user chose.
    """

    __tablename__ = "vcards"

    id = db.Column(db.Integer, primary_key=True)

    # Public URL segment: /v/<slug>. Readable and stable once created.
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    # Label used in the admin listing and on the downloaded QR filename.
    qr_name = db.Column(db.String(150), nullable=False)

    # ---- Design ----
    primary_color = db.Column(db.String(7), nullable=False, default="#527AC9")
    secondary_color = db.Column(db.String(7), nullable=False, default="#7EC09F")

    # ---- Personal information ----
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    image_filename = db.Column(db.String(255))

    # ---- Company details ----
    company = db.Column(db.String(200))
    profession = db.Column(db.String(200))
    summary = db.Column(db.Text)

    # ---- Location ----
    address_line = db.Column(db.String(300))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(120))

    # Show the "Add contact" button at the top of the page instead of inline
    show_add_contact = db.Column(db.Boolean, nullable=False, default=True)

    # ---- QR ----
    qr_filename = db.Column(db.String(255))
    qr_target_url = db.Column(db.String(500))
    qr_short_url = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    links = db.relationship(
        "VCardLink",
        backref="vcard",
        cascade="all, delete-orphan",
        order_by="VCardLink.sort_order",
        lazy="selectin",
    )

    # ---- Convenience accessors used by the templates ----
    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    @property
    def role_line(self) -> str:
        """'Account manager at Firm ABC', or whichever half exists."""
        if self.profession and self.company:
            return f"{self.profession} at {self.company}"
        return self.profession or self.company or ""

    @property
    def formatted_address(self) -> str:
        parts = [self.address_line, self.city, self.state, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)

    def links_of(self, kind: str):
        return [link for link in self.links if link.kind == kind]

    @property
    def phones(self):
        return self.links_of("phone")

    @property
    def emails(self):
        return self.links_of("email")

    @property
    def websites(self):
        return self.links_of("website")

    @property
    def socials(self):
        return self.links_of("social")

    def __repr__(self):
        return f"<VCard {self.slug}>"


class VCardLink(db.Model):
    """One phone / email / website / social entry belonging to a vCard."""

    __tablename__ = "vcard_links"

    id = db.Column(db.Integer, primary_key=True)
    vcard_id = db.Column(
        db.Integer, db.ForeignKey("vcards.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 'phone' | 'email' | 'website' | 'social'
    kind = db.Column(db.String(20), nullable=False, index=True)
    # For socials: the platform key (instagram, linkedin, ...). Blank otherwise.
    platform = db.Column(db.String(40))
    value = db.Column(db.String(500), nullable=False)
    # Caption shown next to the entry, e.g. "Work", "Follow me"
    label = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<VCardLink {self.kind}:{self.value}>"