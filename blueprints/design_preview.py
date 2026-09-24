"""Laboratório visual do redesign do admin — rota protegida, isolada das
rotas reais (nenhum template aqui estende admin_base.html, nenhuma view
toca o banco). Dado 100% mockado, só pra provar a experiência antes de
tocar em qualquer página em produção. Ver CLAUDE.md pra decisão de
arquitetura completa."""

from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template
from flask_login import login_required

from blueprints.auth import require_staff

_PT_WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

design_preview_bp = Blueprint("design_preview", __name__, url_prefix="/admin/design-preview")
design_preview_bp.before_request(require_staff)

_NOW = datetime(2026, 9, 24, 9, 15)


def _at(days=0, hours=0, minutes=0):
    return _NOW + timedelta(days=days, hours=hours, minutes=minutes)


MOCK_CLIENTS = [
    {
        "id": 1,
        "full_name": "Mariana Alves",
        "initials": "MA",
        "service": "Consultoria Versa Completa",
        "stage": "dossie",
        "stage_label": "Dossiê em desenvolvimento",
        "next_action": "Assinatura Visual",
        "next_action_date": _at(days=2),
        "last_contact": None,
        "since": _at(days=-38),
    },
    {
        "id": 2,
        "full_name": "Juliana Costa",
        "initials": "JC",
        "service": "Planejamento de Imagem",
        "stage": "diagnostico_agendado",
        "stage_label": "Aguardando diagnóstico",
        "next_action": None,
        "next_action_date": None,
        "last_contact": "ontem",
        "since": _at(days=-4),
    },
    {
        "id": 3,
        "full_name": "Renata Lima",
        "initials": "RL",
        "service": "Consultoria Versa Completa",
        "stage": "evolucao",
        "stage_label": "Em acompanhamento",
        "next_action": "Follow-up",
        "next_action_date": _at(days=0, hours=7, minutes=45),
        "last_contact": None,
        "since": _at(days=-120),
    },
    {
        "id": 4,
        "full_name": "Carolina Mendes",
        "initials": "CM",
        "service": "Consultoria Versa Completa",
        "stage": "dossie",
        "stage_label": "Dossiê estratégico em revisão",
        "next_action": "Finalizar dossiê",
        "next_action_date": _at(days=1),
        "last_contact": "há 2 dias",
        "since": _at(days=-61),
    },
    {
        "id": 5,
        "full_name": "Ana Beatriz Souza",
        "initials": "AS",
        "service": "Planejamento de Imagem",
        "stage": "proposta_enviada",
        "stage_label": "Proposta enviada — sem resposta",
        "next_action": None,
        "next_action_date": None,
        "last_contact": "há 5 dias",
        "since": _at(days=-9),
    },
    {
        "id": 6,
        "full_name": "Fernanda Ribeiro",
        "initials": "FR",
        "service": "Consultoria Versa Completa",
        "stage": "lead",
        "stage_label": "Novo lead — aguardando contato",
        "next_action": None,
        "next_action_date": None,
        "last_contact": None,
        "since": _at(days=-1),
    },
]

MOCK_CLIENT_DETAILS = {
    1: {  # Mariana Alves — dossiê em desenvolvimento
        "since": _at(days=-38),
        "last_interaction": _at(days=0, hours=-2, minutes=-5),
        "next_meeting": _at(days=2, hours=1, minutes=45),
        "journey": [
            {"key": "identidade", "label": "Identidade", "status": "done"},
            {"key": "diagnostico", "label": "Diagnóstico", "status": "done"},
            {"key": "dossie", "label": "Dossiê", "status": "current"},
            {"key": "looks", "label": "Assinatura Visual", "status": "pending"},
            {"key": "evolucao", "label": "Evolução", "status": "pending"},
        ],
        "next_action": {
            "title": "Preparar sessão de Assinatura Visual",
            "deadline": "em 2 dias",
            "cta": "Continuar Dossiê",
        },
        "timeline": [
            {"time": _at(days=0, hours=-2, minutes=-5), "text": "Fotos recebidas para o dossiê", "channel": "Portal"},
            {"time": _at(days=-1), "text": "Sessão presencial realizada — closet + provas", "channel": "Presencial"},
            {"time": _at(days=-3), "text": "Mensagem: dúvida sobre paleta de cores", "channel": "WhatsApp"},
            {"time": _at(days=-6), "text": "Questionário de diagnóstico concluído", "channel": "Portal"},
            {"time": _at(days=-9), "text": "Fabiana registrou observação sobre objetivo de carreira", "channel": "Admin"},
            {"time": _at(days=-38), "text": "Consultoria contratada", "channel": "Admin"},
        ],
    },
    2: {  # Juliana Costa — aguardando diagnóstico
        "since": _at(days=-4),
        "last_interaction": _at(days=-1),
        "next_meeting": _at(days=0, hours=5, minutes=15),
        "journey": [
            {"key": "identidade", "label": "Identidade", "status": "done"},
            {"key": "diagnostico", "label": "Diagnóstico", "status": "current"},
            {"key": "dossie", "label": "Dossiê", "status": "pending"},
            {"key": "looks", "label": "Assinatura Visual", "status": "pending"},
            {"key": "evolucao", "label": "Evolução", "status": "pending"},
        ],
        "next_action": {
            "title": "Concluir questionário de diagnóstico",
            "deadline": "amanhã",
            "cta": "Ver Diagnóstico",
        },
        "timeline": [
            {"time": _at(days=-1), "text": "Respondeu ao primeiro contato via WhatsApp", "channel": "WhatsApp"},
            {"time": _at(days=-2), "text": "Closet Estratégico agendado", "channel": "Admin"},
            {"time": _at(days=-4), "text": "Lead cadastrada — formulário do site", "channel": "Portal"},
        ],
    },
    3: {  # Renata Lima — em acompanhamento
        "since": _at(days=-120),
        "last_interaction": _at(days=-5),
        "next_meeting": _at(days=0, hours=7, minutes=45),
        "journey": [
            {"key": "identidade", "label": "Identidade", "status": "done"},
            {"key": "diagnostico", "label": "Diagnóstico", "status": "done"},
            {"key": "dossie", "label": "Dossiê", "status": "done"},
            {"key": "looks", "label": "Assinatura Visual", "status": "done"},
            {"key": "evolucao", "label": "Evolução", "status": "current"},
        ],
        "next_action": {
            "title": "Follow-up de acompanhamento",
            "deadline": "hoje, 17:00",
            "cta": "Ver Evolução",
        },
        "timeline": [
            {"time": _at(days=-5), "text": "Provou looks selecionados na sessão de Assinatura Visual", "channel": "Presencial"},
            {"time": _at(days=-20), "text": "Dossiê finalizado e entregue", "channel": "Admin"},
            {"time": _at(days=-45), "text": "Consultoria de coloração realizada", "channel": "Presencial"},
            {"time": _at(days=-120), "text": "Consultoria contratada", "channel": "Admin"},
        ],
    },
    4: {  # Carolina Mendes — dossiê estratégico em revisão
        "since": _at(days=-61),
        "last_interaction": _at(days=-2),
        "next_meeting": _at(days=3, hours=1),
        "journey": [
            {"key": "identidade", "label": "Identidade", "status": "done"},
            {"key": "diagnostico", "label": "Diagnóstico", "status": "done"},
            {"key": "dossie", "label": "Dossiê", "status": "current"},
            {"key": "looks", "label": "Assinatura Visual", "status": "pending"},
            {"key": "evolucao", "label": "Evolução", "status": "pending"},
        ],
        "next_action": {
            "title": "Finalizar Dossiê Estratégico",
            "deadline": "amanhã",
            "cta": "Continuar Dossiê",
        },
        "timeline": [
            {"time": _at(days=-2), "text": "Mensagem: dúvida sobre prazo de entrega do dossiê", "channel": "WhatsApp"},
            {"time": _at(days=-5), "text": "Fabiana revisou rascunho do dossiê", "channel": "Admin"},
            {"time": _at(days=-18), "text": "Sessão presencial — closet e provas", "channel": "Presencial"},
            {"time": _at(days=-61), "text": "Consultoria contratada", "channel": "Admin"},
        ],
    },
    5: {  # Ana Beatriz Souza — proposta enviada, sem resposta
        "since": _at(days=-9),
        "last_interaction": _at(days=-5),
        "next_meeting": _at(days=1, hours=3),
        "journey": [
            {"key": "identidade", "label": "Identidade", "status": "current"},
            {"key": "diagnostico", "label": "Diagnóstico", "status": "pending"},
            {"key": "dossie", "label": "Dossiê", "status": "pending"},
            {"key": "looks", "label": "Assinatura Visual", "status": "pending"},
            {"key": "evolucao", "label": "Evolução", "status": "pending"},
        ],
        "next_action": {
            "title": "Fazer follow-up da proposta",
            "deadline": "hoje",
            "cta": "Registrar contato",
        },
        "timeline": [
            {"time": _at(days=-5), "text": "Proposta enviada por e-mail", "channel": "Admin"},
            {"time": _at(days=-7), "text": "Diagnóstico preliminar realizado", "channel": "Presencial"},
            {"time": _at(days=-9), "text": "Lead cadastrada — indicação", "channel": "Admin"},
        ],
    },
    6: {  # Fernanda Ribeiro — novo lead, aguardando contato
        "since": _at(days=-1),
        "last_interaction": _at(days=-1),
        "next_meeting": _at(days=1, hours=2),
        "journey": [
            {"key": "identidade", "label": "Identidade", "status": "current"},
            {"key": "diagnostico", "label": "Diagnóstico", "status": "pending"},
            {"key": "dossie", "label": "Dossiê", "status": "pending"},
            {"key": "looks", "label": "Assinatura Visual", "status": "pending"},
            {"key": "evolucao", "label": "Evolução", "status": "pending"},
        ],
        "next_action": {
            "title": "Fazer primeiro contato",
            "deadline": "hoje",
            "cta": "Registrar contato",
        },
        "timeline": [
            {"time": _at(days=-1), "text": "Lead cadastrada — formulário do site", "channel": "Portal"},
        ],
    },
}

MOCK_TODAY_AGENDA = [
    {
        "time": _at(days=0, hours=1, minutes=-15),
        "title": "Diagnóstico Versa",
        "client_name": "Mariana Alves",
        "client_id": 1,
        "mode": "online",
        "duration": 60,
        "status": "confirmada",
        "prep_ready": True,
        "questionnaire_received": True,
        "ai_notes": 2,
    },
    {
        "time": _at(days=0, hours=5, minutes=15),
        "title": "Closet Estratégico",
        "client_name": "Juliana Costa",
        "client_id": 2,
        "mode": "presencial",
        "location": "Jardins, São Paulo",
        "duration": 90,
        "status": "agendada",
        "prep_ready": False,
        "questionnaire_received": True,
        "ai_notes": 0,
    },
    {
        "time": _at(days=0, hours=7, minutes=45),
        "title": "Follow-up",
        "client_name": "Renata Lima",
        "client_id": 3,
        "mode": "online",
        "duration": 30,
        "status": "agendada",
        "prep_ready": False,
        "questionnaire_received": False,
        "ai_notes": 0,
    },
]


def _upcoming_day_label(days_ahead, is_tomorrow=False):
    day = _at(days=days_ahead)
    prefix = "Amanhã" if is_tomorrow else _PT_WEEKDAYS[day.weekday()]
    return f"{prefix}, {day.day:02d} set"


MOCK_UPCOMING_DAYS = [
    {"label": _upcoming_day_label(1, is_tomorrow=True), "count": 2},
    {"label": _upcoming_day_label(2), "count": 1},
    {"label": _upcoming_day_label(5), "count": 3},
]

MOCK_NEEDS_ATTENTION = [
    {"text": "Dossiê de Carolina Mendes aguardando revisão", "href_client_id": 4},
    {"text": "Mariana respondeu o questionário de diagnóstico", "href_client_id": 1},
    {"text": "Pagamento de Juliana Costa vence amanhã", "href_client_id": 2},
]

MOCK_CONTENT = {
    "featured": {
        "title": "Talvez você não tenha perdido seu estilo.\nVocê só mudou.",
        "status": "Em desenvolvimento",
        "objective": "Reconhecimento + reflexão",
        "updated": "ontem, 18:42",
    },
    "derivations": [
        {"channel": "Instagram", "status": "Roteiro pendente", "done": False},
        {"channel": "LinkedIn", "status": "Adaptação pendente", "done": False},
        {"channel": "Newsletter", "status": "Resumo pendente", "done": False},
        {"channel": "Google", "status": "Aguardando publicação", "done": False},
    ],
    "upcoming": [
        {"date": "01 out", "label": "Artigo principal"},
        {"date": "04 out", "label": "Instagram"},
        {"date": "08 out", "label": "LinkedIn"},
        {"date": "12 out", "label": "Newsletter"},
    ],
    "in_review_count": 1,
}

# As 4 etapas vêm literalmente de templates/metodo_versa.html (a única
# página que já existe sobre o método) — não inventadas aqui.
METODO_VERSA_STRUCTURE = [
    {"n": 1, "title": "Diagnóstico", "desc": "Mapeamento da imagem atual, momento de carreira e objetivos."},
    {"n": 2, "title": "Estratégia", "desc": "Definição do posicionamento de imagem alinhado à identidade e aos objetivos profissionais."},
    {"n": 3, "title": "Transformação", "desc": "Aplicação prática: estilo, coloração, visagismo e guarda-roupa estratégico."},
    {"n": 4, "title": "Acompanhamento", "desc": "Consolidação dos resultados e ajustes contínuos ao longo da jornada."},
]

METODO_VERSA_TOOLS = ["Diagnóstico", "Dossiê", "Assinatura Visual", "Templates", "Exercícios"]

METODO_VERSA_INSIGHTS = [
    {
        "text": "Clientes relatam dificuldade recorrente em traduzir mudanças "
        "profissionais para o guarda-roupa — a mudança de cargo acontece, "
        "mas o armário continua o mesmo.",
        "origin": "3 atendimentos",
    },
    {
        "text": "Consultorias de closet presenciais geram mais peças "
        "reaproveitadas do que compras novas — sinal de que a curadoria "
        "do que já existe é subestimada.",
        "origin": "2 atendimentos",
    },
]


def _find_client(client_id):
    for c in MOCK_CLIENTS:
        if c["id"] == client_id:
            return c
    return None


@design_preview_bp.route("/")
@login_required
def hoje():
    return render_template(
        "design_preview/hoje.html",
        next_activity=MOCK_TODAY_AGENDA[0],
        today_agenda=MOCK_TODAY_AGENDA,
        needs_attention=MOCK_NEEDS_ATTENTION,
        continue_item=MOCK_CLIENTS[3],
        business={
            "active_clients": 12,
            "contracted_value": "34.600",
            "leads_deciding": 3,
            "followups_this_week": 2,
        },
        now=_NOW,
        today_label=f"{_PT_WEEKDAYS[_NOW.weekday()]}, {_NOW.strftime('%d/%m')}",
    )


@design_preview_bp.route("/clientes")
@login_required
def clientes():
    return render_template("design_preview/clientes.html", clients=MOCK_CLIENTS, now=_NOW)


@design_preview_bp.route("/clientes/<int:client_id>")
@login_required
def cliente_360(client_id):
    client = _find_client(client_id)
    detail = MOCK_CLIENT_DETAILS.get(client_id)
    if client is None or detail is None:
        abort(404)
    return render_template(
        "design_preview/cliente_360.html",
        client=client,
        detail=detail,
        now=_NOW,
    )


@design_preview_bp.route("/agenda")
@login_required
def agenda():
    return render_template(
        "design_preview/agenda.html",
        today_agenda=MOCK_TODAY_AGENDA,
        upcoming_days=MOCK_UPCOMING_DAYS,
        now=_NOW,
        today_label=f"{_PT_WEEKDAYS[_NOW.weekday()]}, {_NOW.day} de setembro",
    )


@design_preview_bp.route("/conteudo")
@login_required
def conteudo():
    return render_template("design_preview/conteudo.html", content=MOCK_CONTENT)


@design_preview_bp.route("/metodo-versa")
@login_required
def metodo_versa():
    return render_template(
        "design_preview/metodo_versa.html",
        structure=METODO_VERSA_STRUCTURE,
        tools=METODO_VERSA_TOOLS,
        insights=METODO_VERSA_INSIGHTS,
    )
