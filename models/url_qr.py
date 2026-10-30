from datetime import datetime

from extensions import db


class UrlQR(db.Model):
    """
    A QR code pointing at any external URL.

    The QR encodes target_url exactly as entered. short_url is a legacy
    column from an earlier link-shortener and is no longer filled in.
    """

    __tablename__ = "url_qrs"

    id = db.Column(db.Integer, primary_key=True)

    # Owning account. Nullable so pre-migration rows stay valid; the app
    # assigns any un-owned row to the admin on boot.
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    name = db.Column(db.String(150), nullable=False)
    target_url = db.Column(db.String(1000), nullable=False)
    short_url = db.Column(db.String(500), nullable=True)
    qr_filename = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def encoded_url(self) -> str:
        """The address the QR opens."""
        return self.target_url

    def __repr__(self):
        return f"<UrlQR {self.name}>"
