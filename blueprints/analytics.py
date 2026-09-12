from flask import Blueprint, render_template
from flask_login import login_required

from blueprints.auth import require_staff
from models import LEAD_SOURCES, Client, Consultation, Payment

analytics_bp = Blueprint("analytics", __name__, url_prefix="/painel/analytics")
analytics_bp.before_request(require_staff)


@analytics_bp.route("/")
@login_required
def index():
    # Contagem de clientes por status já aparece nas colunas do Kanban do
    # Painel — não repetida aqui, pra Analytics só mostrar o que não existe
    # em nenhum outro lugar do painel (ver revisão de navegação Estúdio/Negócio).
    clients_by_source = {key: Client.query.filter_by(source=key).count() for key, _label in LEAD_SOURCES}

    revenue_paid = sum(p.amount for p in Payment.query.filter_by(status="pago").all())
    revenue_pending = sum(p.amount for p in Payment.query.filter_by(status="pendente").all())
    revenue_overdue = sum(p.amount for p in Payment.query.filter_by(status="atrasado").all())

    recurring_clients = sum(1 for c in Client.query.all() if c.is_recorrente)

    return render_template(
        "analytics.html",
        total_clients=Client.query.count(),
        clients_by_source=clients_by_source,
        revenue_paid=revenue_paid,
        revenue_pending=revenue_pending,
        revenue_overdue=revenue_overdue,
        upcoming_sessions=Consultation.query.filter_by(status="agendada").count(),
        recurring_clients=recurring_clients,
    )
