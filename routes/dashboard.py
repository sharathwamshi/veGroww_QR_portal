from flask import Blueprint, render_template

from models import Batch, IDCard, ImageQR, Invitation, UpiQR, UrlQR, VCard
from utils.decorators import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def home():
    stats = {
        "batches": Batch.query.count(),
        "total_cards": IDCard.query.count(),
        "generated_cards": IDCard.query.filter_by(status="generated").count(),
        "pending_cards": IDCard.query.filter(IDCard.status != "generated").count(),
        "image_qrs": ImageQR.query.count(),
        "upi_qrs": UpiQR.query.count(),
        "vcards": VCard.query.count(),
        "url_qrs": UrlQR.query.count(),
        "invitations": Invitation.query.count(),
    }
    recent_batches = Batch.query.order_by(Batch.created_at.desc()).limit(5).all()
    return render_template("dashboard.html", stats=stats, recent_batches=recent_batches)