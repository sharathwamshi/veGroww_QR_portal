from datetime import datetime

from extensions import db


class Batch(db.Model):
    """
    A Batch groups a set of ID cards under one company identity.

    All the "global" options the portal exposes - company name, address,
    logo and the issuing authority's signature - live here so they only
    need to be set once per batch and every card generated within it
    reuses them automatically.
    """

    __tablename__ = "batches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

    company_name = db.Column(db.String(200), nullable=False)
    company_address = db.Column(db.String(400), nullable=False)

    logo_filename = db.Column(db.String(255), nullable=True)
    signature_filename = db.Column(db.String(255), nullable=True)
    signature_label = db.Column(db.String(150), nullable=True, default="Issuing Authority")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cards = db.relationship(
        "IDCard", backref="batch", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def total_cards(self):
        return self.cards.count()

    @property
    def generated_cards(self):
        return self.cards.filter_by(status="generated").count()

    @property
    def pending_cards(self):
        from .id_card import IDCard  # local import avoids circular import at module load

        return self.cards.filter(IDCard.status != "generated").count()

    def __repr__(self):
        return f"<Batch {self.name}>"
