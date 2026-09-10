from flask import Blueprint, render_template
from flask_login import login_required

from blueprints.auth import require_staff
from models import CLIENT_STATUSES, LEAD_SOURCES, Client, Consultation, Payment

analytics_bp = Blueprint("analytics", __name__, url_prefix="/painel/analytics")
analytics_bp.before_request(require_staff)


@analytics_bp.route("/")
@login_required
def index():
    clients_by_status = {key: Client.query.filter_by(status=key).count() for key, _label in CLIENT_STATUSES}
    clients_by_source = {key: Client.query.filter_by(source=key).count() for key, _label in LEAD_SOURCES}

    revenue_paid = sum(p.amount for p in Payment.query.filter_by(status="pago").all())
    revenue_pending = sum(p.amount for p in Payment.query.filter_by(status="pendente").all())
    revenue_overdue = sum(p.amount for p in Payment.query.filter_by(status="atrasado").all())

    return render_template(
        "analytics.html",
        total_clients=Client.query.count(),
        clients_by_status=clients_by_status,
        clients_by_source=clients_by_source,
        revenue_paid=revenue_paid,
        revenue_pending=revenue_pending,
        revenue_overdue=revenue_overdue,
        upcoming_sessions=Consultation.query.filter_by(status="agendada").count(),
    )
