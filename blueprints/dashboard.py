from flask import Blueprint, render_template
from flask_login import login_required

from models import CLIENT_STATUSES, Client, Consultation, Payment

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/painel")


@dashboard_bp.route("/")
@login_required
def index():
    clients_by_status = {
        key: Client.query.filter_by(status=key).order_by(Client.created_at.desc()).all()
        for key, _label in CLIENT_STATUSES
    }
    upcoming = (
        Consultation.query.filter_by(status="agendada")
        .order_by(Consultation.scheduled_at.asc())
        .limit(10)
        .all()
    )
    pending_payments = (
        Payment.query.filter_by(status="pendente").order_by(Payment.due_date.asc()).limit(10).all()
    )
    return render_template(
        "dashboard.html",
        clients_by_status=clients_by_status,
        upcoming=upcoming,
        pending_payments=pending_payments,
    )
