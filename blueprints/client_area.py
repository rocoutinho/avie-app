"""Área do próprio cliente — ele loga com e-mail/senha (senha definida por
um staff em /painel/clientes, ver blueprints/clients.py) e vê só os dados
dele mesmo: diagnóstico e relatórios/recomendações já enviados. Nunca lista
outros clientes nem dá acesso a nada de /painel."""

from datetime import datetime

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from extensions import db
from journey import build_journey
from models import Client, CLOSET_ITEM_CATEGORIES, Look, LOOK_MOMENTS, ShoppingListItem

client_area_bp = Blueprint("client_area", __name__, url_prefix="/minha-area")


def require_client():
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not isinstance(current_user, Client):
        abort(403)


client_area_bp.before_request(require_client)


# icon_key casa com o macro service_icon() em templates/client_area.html.
# Rótulos e nomes de coluna não batem 1:1 de propósito — os nomes de
# coluna (estilo_pessoal, proporcoes, coloracao) vêm de antes da marca
# definir esses 5 nomes de serviço; ver comentário em models.py:StyleReport.
DOSSIE_SERVICE_LABELS = [
    ("estilo_pessoal", "Estilo", "estilo"),
    ("proporcoes", "Biotipo", "biotipo"),
    ("coloracao", "Cores", "cores"),
    ("visagismo", "Visagismo", "visagismo"),
    ("arquetipos", "Arquétipos", "arquetipos"),
]


def _sent_reports(client):
    return [r for r in client.reports if r.status == "enviado"]


def _dossie_services(sent_reports):
    # Clientes cadastrados via dossiê (ver blueprints/clients.py:new_client_with_dossie)
    # já chegam com o diagnóstico feito fora do sistema — em vez do CTA
    # "faça seu diagnóstico" (que é pro funil público do zero), mostramos
    # um card por serviço já entregue, juntando os campos de todos os
    # relatórios enviados (o mais recente prevalece se mais de um cobrir
    # o mesmo serviço).
    services = []
    for field, label, icon_key in DOSSIE_SERVICE_LABELS:
        text = next((getattr(r, field) for r in sent_reports if getattr(r, field, None)), None)
        if text:
            services.append({"label": label, "text": text, "icon": icon_key})
    return services


@client_area_bp.route("/")
@login_required
def index():
    """Resumo de leitura rápida — nenhum conteúdo completo mora aqui, só
    status e um resumo de uma linha por etapa; cada card leva pra sua
    própria página (mesmo padrão dos 4 recursos, sem exceção — ver revisão
    de UX da área da cliente). O destaque no topo prioriza o que é mais
    acionável: próxima consultoria > novidade desde a última visita >
    mensagem padrão de último acesso."""
    previous_login_raw = session.pop("client_previous_login_at", None)
    previous_login = datetime.fromisoformat(previous_login_raw) if previous_login_raw else None

    sent_reports = _sent_reports(current_user)
    dossie_services = _dossie_services(sent_reports)

    has_news = previous_login is not None and (
        any(r.sent_at and r.sent_at > previous_login for r in sent_reports)
        or any(l.created_at and l.created_at > previous_login for l in current_user.looks)
    )

    return render_template(
        "client_area.html",
        client=current_user,
        previous_login=previous_login,
        has_news=has_news,
        journey=build_journey(current_user),
        dossie_services=dossie_services,
    )


@client_area_bp.route("/identidade")
@login_required
def identity():
    return render_template("client_area_identity.html", client=current_user)


@client_area_bp.route("/diagnostico")
@login_required
def diagnostico():
    sent_reports = _sent_reports(current_user)
    return render_template(
        "client_area_diagnostico.html",
        client=current_user,
        dossie_services=_dossie_services(sent_reports),
        # "Recomendações da consultoria" só mostra relatórios que não são
        # dossiês estruturados (senão duplicaria o mesmo conteúdo já
        # detalhado nos cards de serviço acima).
        other_reports=[r for r in sent_reports if not r.is_dossie],
    )


@client_area_bp.route("/looks")
@login_required
def looks():
    """"Minha assinatura visual" é um hub, não uma página de conteúdo — só
    o resumo do topo e os 3 cards de navegação (Meus looks, Meu closet,
    Próximas peças), mesmo padrão visual/estrutural do hub da cliente pro
    staff (client_detail.html, classes .journey-grid/.journey-card já
    existentes, reaproveitadas aqui sem CSS novo). Cada card leva pra sua
    própria página com o conteúdo completo e os filtros — nada de conteúdo
    completo mora aqui, mesma regra do resto da área da cliente (ver
    client_area.index)."""
    return render_template("client_area_looks.html", client=current_user)


@client_area_bp.route("/looks/galeria")
@login_required
def looks_gallery():
    active_momento = request.args.get("momento") or None
    looks = current_user.looks
    if active_momento:
        looks = [l for l in looks if l.momento == active_momento]
    momento_counts = {key: sum(1 for l in current_user.looks if l.momento == key) for key, _label in LOOK_MOMENTS}

    return render_template(
        "client_area_looks_gallery.html",
        client=current_user,
        looks=looks,
        active_momento=active_momento,
        momento_counts=momento_counts,
    )


@client_area_bp.route("/closet")
@login_required
def closet():
    active_categoria = request.args.get("categoria") or None
    closet_items = current_user.closet_items
    if active_categoria:
        closet_items = [i for i in closet_items if i.category == active_categoria]
    categoria_counts = {
        key: sum(1 for i in current_user.closet_items if i.category == key) for key, _label in CLOSET_ITEM_CATEGORIES
    }

    return render_template(
        "client_area_closet.html",
        client=current_user,
        closet_items=closet_items,
        active_categoria=active_categoria,
        categoria_counts=categoria_counts,
    )


@client_area_bp.route("/personal-shopper")
@login_required
def personal_shopper():
    return render_template(
        "client_area_personal_shopper.html",
        client=current_user,
        shopping_list_items=current_user.shopping_list_items,
    )


@client_area_bp.route("/evolucao")
@login_required
def evolucao():
    now = datetime.utcnow()
    future = sorted(
        (c for c in current_user.consultations if c.status == "agendada" and c.scheduled_at >= now),
        key=lambda c: c.scheduled_at,
    )
    next_consultation = future[0] if future else None
    future_ids = {c.id for c in future}
    # current_user.consultations já vem ordenada por scheduled_at desc
    # (ver models.py) — filtrar preserva essa ordem, então past_consultations
    # já sai com a mais recente primeiro, sem precisar reordenar.
    past_consultations = [c for c in current_user.consultations if c.id not in future_ids]
    return render_template(
        "client_area_evolucao.html",
        client=current_user,
        next_consultation=next_consultation,
        past_consultations=past_consultations,
    )


@client_area_bp.route("/looks/<int:look_id>/favoritar", methods=["POST"])
@login_required
def toggle_look_favorite(look_id):
    # Só a própria cliente favorita os próprios looks — nunca recebe
    # client_id por parâmetro, sempre filtra pelo current_user (ver guard
    # require_client acima).
    look = Look.query.filter_by(id=look_id, client_id=current_user.id).first_or_404()
    look.favorited = not look.favorited
    db.session.commit()
    return redirect(url_for("client_area.looks_gallery"))


@client_area_bp.route("/lista-compras/<int:item_id>/aceitar", methods=["POST"])
@login_required
def accept_shopping_list_item(item_id):
    """Primeira ação de escrita da cliente no Personal Shopper: só pra
    recomendações com link_compra e ainda "recomendada" — aceitar move pro
    status "aprovada" já existente (mesmo vocabulário que a consultora usa
    manualmente), não cria estado novo. Filtra sempre por current_user, nunca
    recebe client_id (mesmo padrão de segurança de toggle_look_favorite)."""
    item = ShoppingListItem.query.filter_by(id=item_id, client_id=current_user.id).first_or_404()
    if item.link_compra and item.status == "recomendada":
        item.status = "aprovada"
        db.session.commit()
    return redirect(url_for("client_area.personal_shopper"))
