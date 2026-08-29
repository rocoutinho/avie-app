"""Área do próprio cliente — ele loga com e-mail/senha (senha definida por
um staff em /painel/clientes, ver blueprints/clients.py) e vê só os dados
dele mesmo: diagnóstico e relatórios/recomendações já enviados. Nunca lista
outros clientes nem dá acesso a nada de /painel."""

from datetime import datetime

from flask import Blueprint, abort, current_app, render_template, session
from flask_login import current_user, login_required

from models import Client

client_area_bp = Blueprint("client_area", __name__, url_prefix="/minha-area")


def require_client():
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not isinstance(current_user, Client):
        abort(403)


client_area_bp.before_request(require_client)


# icon_key casa com o macro service_icon() em templates/client_area.html
# (mesmos ícones/paths usados pros "pilares" da consultoria em
# landing.html, pra área do cliente falar a mesma linguagem visual da
# página pública, sem acoplar as duas templates).
DOSSIE_SERVICE_LABELS = [
    ("estilo_pessoal", "Estilo pessoal", "hanger"),
    ("proporcoes", "Proporções", "ruler"),
    ("coloracao", "Coloração", "palette"),
    ("visagismo", "Visagismo", "sparkle"),
]


@client_area_bp.route("/")
@login_required
def index():
    previous_login_raw = session.pop("client_previous_login_at", None)
    previous_login = datetime.fromisoformat(previous_login_raw) if previous_login_raw else None
    sent_reports = [r for r in current_user.reports if r.status == "enviado"]

    # Clientes cadastrados via dossiê (ver blueprints/clients.py:new_client_with_dossie)
    # já chegam com o diagnóstico feito fora do sistema — em vez do CTA
    # "faça seu diagnóstico" (que é pro funil público do zero), mostramos
    # um card por serviço já entregue, juntando os campos de todos os
    # relatórios enviados (o mais recente prevalece se mais de um cobrir
    # o mesmo serviço).
    dossie_services = []
    for field, label, icon_key in DOSSIE_SERVICE_LABELS:
        text = next((getattr(r, field) for r in sent_reports if getattr(r, field, None)), None)
        if text:
            dossie_services.append({"label": label, "text": text, "icon": icon_key})

    # "Recomendações da consultoria" só mostra relatórios que não são
    # dossiês estruturados (senão duplicaria o mesmo conteúdo já
    # detalhado nos cards de serviço acima).
    other_reports = [
        r for r in sent_reports if not any(getattr(r, field, None) for field, _, _ in DOSSIE_SERVICE_LABELS)
    ]

    return render_template(
        "client_area.html",
        client=current_user,
        previous_login=previous_login,
        other_reports=other_reports,
        dossie_services=dossie_services,
    )
