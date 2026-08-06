from datetime import datetime

from extensions import db


class IDCard(db.Model):
    """
    A single employee ID card entry.

    Field names mirror the reference employee data sheet (Sr. No, Name,
    Employee Code, Blood Group, Landline, Emergency Contact, Employee
    Contact) with a photo attached per-card. Company-wide details
    (name/address/logo/signature) are inherited from the parent Batch.
    """

    __tablename__ = "id_cards"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)

    sr_no = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(150), nullable=False)
    employee_code = db.Column(db.String(50), nullable=False, index=True)
    designation = db.Column(db.String(150), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)

    landline = db.Column(db.String(30), nullable=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
    employee_contact = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), nullable=True)

    photo_filename = db.Column(db.String(255), nullable=True)

    # Generated artefacts
    card_filename = db.Column(db.String(255), nullable=True)
    qr_filename = db.Column(db.String(255), nullable=True)
    qr_short_url = db.Column(db.String(500), nullable=True)
    qr_target_url = db.Column(db.String(500), nullable=True)

    # pending_photo -> awaiting a photo upload before a card can be rendered
    # ready       -> photo present, card not generated yet
    # generated   -> card + QR generated and available for download
    status = db.Column(db.String(20), nullable=False, default="pending_photo")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("batch_id", "employee_code", name="uq_batch_employee_code"),
    )

    def refresh_status(self):
        if self.card_filename and self.qr_filename:
            self.status = "generated"
        elif self.photo_filename:
            self.status = "ready"
        else:
            self.status = "pending_photo"

    def __repr__(self):
        return f"<IDCard {self.employee_code} - {self.name}>"
