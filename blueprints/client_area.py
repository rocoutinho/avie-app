"""Área do próprio cliente — ele loga com e-mail/senha (senha definida por
um staff em /painel/clientes, ver blueprints/clients.py) e vê só os dados
dele mesmo: diagnóstico e relatórios/recomendações já enviados. Nunca lista
outros clientes nem dá acesso a nada de /painel."""

from datetime import datetime

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
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
    ("coloracao", "Coloração", "cores"),
    ("visagismo", "Visagismo", "visagismo"),
    ("arquetipos", "Arquétipos", "arquetipos"),
]


def _sent_reports(client):
    return [r for r in client.reports if r.status == "enviado"]


def _group_dossie_sections(sections):
    """Agrupa as sub-análises de um serviço (models.py:DossieSection) em
    blocos prontos pra renderizar: sem `group`, cada seção vira seu
    próprio bloco de collapse (o padrão — cobre quase todo caso real);
    duas ou mais seções com o mesmo `group` viram um único bloco de abas
    entre elas (usado só quando o conteúdo é genuinamente comparável, ex:
    2 estilos identificados) — ver avaliação de recursos de UI que
    motivou essa regra. `sections` já vem ordenada (order, created_at),
    e essa ordem é preservada tanto entre blocos quanto dentro de cada
    grupo de abas."""
    blocks = []
    groups = {}
    for section in sections:
        if section.group:
            block = groups.get(section.group)
            if block is None:
                block = {"type": "tabs", "sections": []}
                groups[section.group] = block
                blocks.append(block)
            block["sections"].append(section)
        else:
            blocks.append({"type": "collapse", "sections": [section]})
    return blocks


def _dossie_services(client):
    """Um dict por serviço já preenchido no dossiê — texto corrido
    (resumo/obrigatório desde o onboarding) mais as sub-análises
    opcionais dele, já agrupadas em blocos prontos pra renderizar (ver
    _group_dossie_sections). Sem seções cadastradas, um serviço aparece
    exatamente como sempre apareceu (só o texto corrido) — nada muda pra
    dossiês que nunca ganharam esse detalhamento."""
    report = client.dossie_report
    if report is None:
        return []
    services = []
    for field, label, icon_key in DOSSIE_SERVICE_LABELS:
        text = getattr(report, field, None)
        sections = [s for s in report.dossie_sections if s.service == field]
        if text or sections:
            services.append(
                {
                    "label": label,
                    "text": text,
                    "icon": icon_key,
                    "blocks": _group_dossie_sections(sections),
                }
            )
    return services


@client_area_bp.route("/")
@login_required
def index():
    """Resumo de leitura rápida — nenhum conteúdo completo mora aqui, só
    os 4 cards da jornada; cada um leva pra sua própria página (mesmo
    padrão dos 4 recursos, sem exceção — ver revisão de UX da área da
    cliente). Tela deliberadamente sem nenhum texto além do título — sem
    aviso dinâmico, sem mensagem de último/primeiro acesso — por pedido
    explícito de manter a home mínima."""
    journey = build_journey(current_user)
    return render_template("client_area.html", client=current_user, journey=journey)


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
        dossie_services=_dossie_services(current_user),
        # "Recomendações da consultoria" só mostra relatórios que não são
        # dossiês estruturados (senão duplicaria o mesmo conteúdo já
        # detalhado nos cards de serviço acima).
        other_reports=[r for r in sent_reports if not r.is_dossie],
    )


@client_area_bp.route("/looks")
@login_required
def looks():
    """"Minha assinatura visual": um card colapsável "Meus looks" (details/
    summary + carrossel Bootstrap dos looks, mesmo padrão do carrossel de
    Coloração em client_area_diagnostico.html) seguido de 2 cards-botão
    quadrados de navegação — Meu closet e Personal Shopper (reaproveitam
    .home-journey-grid/.home-journey-card da home, sem CSS novo). Só o
    card de looks mostra conteúdo direto aqui (fotos/nome, via carrossel);
    closet e Personal Shopper continuam só navegação — cada um leva pra
    sua própria página com o conteúdo completo e os filtros."""
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
    """"Minha Evolução" responde "o que faço agora", não é agenda nem
    histórico — por isso `recent_achievements` corta pra poucas sessões
    (as 3 mais recentes) e só as realmente concluídas ("realizada"),
    nunca agendamentos cancelados/faltas, que não são "conquista"."""
    now = datetime.utcnow()
    future = sorted(
        (c for c in current_user.consultations if c.status == "agendada" and c.scheduled_at >= now),
        key=lambda c: c.scheduled_at,
    )
    next_consultation = future[0] if future else None
    # current_user.consultations já vem ordenada por scheduled_at desc
    # (ver models.py), então fatiar preserva a mais recente primeiro.
    recent_achievements = [c for c in current_user.consultations if c.status == "realizada"][:3]
    return render_template(
        "client_area_evolucao.html",
        client=current_user,
        next_consultation=next_consultation,
        recent_achievements=recent_achievements,
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
