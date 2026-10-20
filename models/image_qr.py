from datetime import datetime

from extensions import db


class ImageQR(db.Model):
    """A generic uploaded image paired with a QR code that opens it."""

    __tablename__ = "image_qrs"

    id = db.Column(db.Integer, primary_key=True)

    # Owning account. Nullable so pre-migration rows stay valid; the app
    # assigns any un-owned row to the admin on boot.
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    title = db.Column(db.String(150), nullable=False)

    image_filename = db.Column(db.String(255), nullable=False)
    qr_filename = db.Column(db.String(255), nullable=False)

    target_url = db.Column(db.String(500), nullable=False)   # full local/public URL to the image
    short_url = db.Column(db.String(500), nullable=True)     # TinyURL-shortened version, if reachable

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ImageQR {self.title}>"
