from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from blog_engine import format_date_pt
from blueprints.auth import require_staff
from blueprints.client_area import _quote_of_the_day
from metodo_versa_content import METODO_VERSA_STEPS
from models import CLIENT_STATUSES, BlogPost, Client, Consultation, Payment

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/painel")
dashboard_bp.before_request(require_staff)

_PT_WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _greeting(hour):
    if 5 <= hour < 12:
        return "Bom dia"
    if 12 <= hour < 18:
        return "Boa tarde"
    return "Boa noite"


@dashboard_bp.route("/")
@login_required
def index():
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

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

    # "Hoje" (topo do Painel) — ver CLAUDE.md: densidade de um dashboard de
    # verdade, mas todo número vem de contagens/somas já existentes nos
    # mesmos modelos usados pelo Kanban abaixo, nada é dado fictício.
    active_clients = clients_by_status["cliente_ativo"]
    new_active_this_month = sum(1 for c in active_clients if c.created_at and c.created_at >= month_start)

    scheduled_consultations = Consultation.query.filter_by(status="agendada").all()
    consultations_this_week = sum(1 for c in scheduled_consultations if c.scheduled_at >= week_start)

    revenue_month = sum(
        p.amount
        for p in Payment.query.filter_by(status="pago").all()
        if p.paid_at and p.paid_at >= month_start
    )

    posts_in_review = BlogPost.query.filter_by(status="em_revisao").count()

    agenda_today = sorted(
        (c for c in scheduled_consultations if today_start <= c.scheduled_at < today_end),
        key=lambda c: c.scheduled_at,
    )
    next_consultation = min(
        (c for c in scheduled_consultations if c.scheduled_at >= now),
        key=lambda c: c.scheduled_at,
        default=None,
    )

    pipeline_counts = [
        (label, len(clients_by_status[key]))
        for key, label in CLIENT_STATUSES
        if key not in ("cliente_ativo", "cliente_concluido", "perdido")
    ]

    return render_template(
        "dashboard.html",
        clients_by_status=clients_by_status,
        upcoming=upcoming,
        pending_payments=pending_payments,
        greeting=_greeting(now.hour),
        today_label=f"{_PT_WEEKDAYS[now.weekday()]}, {format_date_pt(now.date())}",
        active_clients_count=len(active_clients),
        new_active_this_month=new_active_this_month,
        scheduled_count=len(scheduled_consultations),
        consultations_this_week=consultations_this_week,
        revenue_month=revenue_month,
        posts_in_review=posts_in_review,
        agenda_today=agenda_today,
        next_consultation=next_consultation,
        pipeline_counts=pipeline_counts,
        new_leads_count=len(clients_by_status["lead"]),
        proposals_sent_count=len(clients_by_status["proposta_enviada"]),
        diagnostico_concluido_count=len(clients_by_status["diagnostico_concluido"]),
        attention_count=min(len(pending_payments), 3) + (1 if posts_in_review else 0),
        quote=_quote_of_the_day(),
    )


@dashboard_bp.route("/metodo-versa")
@login_required
def metodo_versa():
    return render_template("metodo_versa_admin.html", steps=METODO_VERSA_STEPS)
