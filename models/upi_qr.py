from datetime import datetime

from extensions import db


class UpiQR(db.Model):
    """A generated UPI payment QR code (upi:// deep-link, UPI-app scannable)."""

    __tablename__ = "upi_qrs"

    id = db.Column(db.Integer, primary_key=True)

    upi_id = db.Column(db.String(150), nullable=False)
    payee_name = db.Column(db.String(150), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    note = db.Column(db.String(200), nullable=True)

    upi_uri = db.Column(db.String(500), nullable=False)   # the raw upi://pay?... string encoded
    qr_filename = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UpiQR {self.upi_id}>"
