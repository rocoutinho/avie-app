from datetime import datetime, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required

from blueprints.auth import require_staff
from models import CONSULTATION_STATUSES, Consultation

sessions_bp = Blueprint("sessions", __name__, url_prefix="/painel/sessoes")
sessions_bp.before_request(require_staff)

_PT_WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Janelas móveis a partir de hoje, não o mês/semana civil — "o que vem por
# aí" importa mais aqui do que alinhar com o calendário. "todas" preserva o
# comportamento de sempre (nenhum filtro de data) e continua o padrão, pra
# não esconder consultas fora da janela de quem abre a Agenda sem escolher
# um período.
_PERIOD_WINDOWS = {"hoje": 1, "semana": 7, "mes": 30}
_PERIOD_LABELS = {"todas": "Todas", "hoje": "Hoje", "semana": "Semana", "mes": "Mês"}


@sessions_bp.route("/")
@login_required
def list_sessions():
    status = request.args.get("status") or None
    periodo = request.args.get("periodo") or "todas"
    if periodo not in _PERIOD_LABELS:
        periodo = "todas"

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    base_query = Consultation.query
    if periodo != "todas":
        window_end = today_start + timedelta(days=_PERIOD_WINDOWS[periodo])
        base_query = base_query.filter(
            Consultation.scheduled_at >= today_start, Consultation.scheduled_at < window_end
        )

    query = base_query
    if status:
        query = query.filter_by(status=status)
    consultations = query.order_by(Consultation.scheduled_at.asc()).all()

    # Contagens dos filtros de status já respeitam o período ativo, pra não
    # mostrar um número que suma da lista ao clicar.
    counts = {
        key: base_query.filter_by(status=key).count() for key, _label in CONSULTATION_STATUSES
    }
    counts["all"] = base_query.count()

    return render_template(
        "sessions_list.html",
        consultations=consultations,
        counts=counts,
        active_status=status,
        active_periodo=periodo,
        period_labels=_PERIOD_LABELS,
        today_label=f"{_PT_WEEKDAYS[now.weekday()]}, {now.day:02d}/{now.month:02d}",
    )
