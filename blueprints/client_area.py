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


@client_area_bp.route("/")
@login_required
def index():
    previous_login_raw = session.pop("client_previous_login_at", None)
    previous_login = datetime.fromisoformat(previous_login_raw) if previous_login_raw else None
    sent_reports = [r for r in current_user.reports if r.status == "enviado"]
    return render_template("client_area.html", client=current_user, previous_login=previous_login, sent_reports=sent_reports)
