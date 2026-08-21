from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

CLIENT_STATUSES = [
    ("lead", "Novo Lead"),
    ("contatado", "Contatado"),
    ("diagnostico_agendado", "Diagnóstico Agendado"),
    ("diagnostico_concluido", "Diagnóstico Concluído"),
    ("proposta_enviada", "Proposta Enviada"),
    ("cliente_ativo", "Cliente Ativo"),
    ("cliente_concluido", "Cliente Concluído"),
    ("perdido", "Perdido / Não avançou"),
]

CONSULTATION_TYPES = [
    ("diagnostico_gratuito", "Diagnóstico Gratuito"),
    ("consultoria_imagem", "Consultoria de Imagem"),
    ("personal_branding", "Personal Branding / Posicionamento"),
    ("manutencao", "Sessão de Manutenção"),
    ("outro", "Outro"),
]

CONSULTATION_STATUSES = [
    ("agendada", "Agendada"),
    ("realizada", "Realizada"),
    ("cancelada", "Cancelada"),
    ("faltou", "Cliente faltou"),
]

REPORT_STATUSES = [
    ("rascunho", "Rascunho"),
    ("enviado", "Enviado"),
]

PAYMENT_STATUSES = [
    ("pendente", "Pendente"),
    ("pago", "Pago"),
    ("atrasado", "Atrasado"),
]

LEAD_SOURCES = [
    ("instagram", "Instagram"),
    ("google", "Google"),
    ("linkedin", "LinkedIn"),
    ("indicacao", "Indicação"),
    ("site", "Site"),
    ("evento", "Evento / Palestra"),
    ("outro", "Outro"),
]

BUDGET_RANGES = [
    ("ate_1500", "Até R$ 1.500"),
    ("1500_3000", "R$ 1.500 – R$ 3.000"),
    ("3000_6000", "R$ 3.000 – R$ 6.000"),
    ("acima_6000", "Acima de R$ 6.000"),
    ("nao_sei", "Ainda não sei"),
]

USER_ROLES = [
    ("owner", "Owner (aprova e publica campanhas)"),
    ("marketing", "Marketing (cria e edita campanhas)"),
]

CAMPAIGN_STATUSES = [
    ("rascunho", "Rascunho"),
    ("em_revisao", "Em revisão"),
    ("publicado", "Publicado"),
    ("arquivado", "Arquivado"),
]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="owner")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Campaign(db.Model):
    """Um criativo de landing page (título, imagem, CTA etc.) que pode ser
    testado numa URL própria (/lp/<slug>) para uma campanha de tráfego
    específica, sem mexer na landing principal. Fluxo: marketing cria como
    rascunho -> envia para revisão -> owner aprova (publica) ou recusa
    (volta pra rascunho, com um motivo opcional)."""

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    internal_name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), default="rascunho", nullable=False)

    hero_eyebrow = db.Column(db.String(150))
    hero_title = db.Column(db.String(255), nullable=False)
    hero_highlight = db.Column(db.String(100))
    hero_subtitle = db.Column(db.Text)
    hero_cta_text = db.Column(db.String(80))
    hero_image_url = db.Column(db.String(500))
    theme_color = db.Column(db.String(20))

    review_note = db.Column(db.Text)

    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    instagram = db.Column(db.String(100))
    source = db.Column(db.String(30), default="outro")
    status = db.Column(db.String(30), default="lead")
    notes = db.Column(db.Text)
    # Atribuição técnica de campanha (parâmetros utm_* capturados na primeira
    # visita) — complementa "source", que é a origem autodeclarada pelo lead.
    utm_source = db.Column(db.String(150))
    utm_medium = db.Column(db.String(150))
    utm_campaign = db.Column(db.String(150))
    utm_content = db.Column(db.String(150))
    utm_term = db.Column(db.String(150))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = db.relationship(
        "StyleProfile", backref="client", uselist=False, cascade="all, delete-orphan"
    )
    consultations = db.relationship(
        "Consultation",
        backref="client",
        cascade="all, delete-orphan",
        order_by="Consultation.scheduled_at.desc()",
    )
    reports = db.relationship(
        "StyleReport",
        backref="client",
        cascade="all, delete-orphan",
        order_by="StyleReport.created_at.desc()",
    )
    payments = db.relationship(
        "Payment",
        backref="client",
        cascade="all, delete-orphan",
        order_by="Payment.created_at.desc()",
    )


class StyleProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), unique=True, nullable=False)

    objetivo_profissional = db.Column(db.Text)
    momento_carreira = db.Column(db.Text)
    como_quer_ser_percebida = db.Column(db.Text)
    desafios_imagem = db.Column(db.Text)
    ambiente_trabalho = db.Column(db.String(255))
    estilo_atual = db.Column(db.Text)
    cores_preferidas = db.Column(db.String(255))
    referencias_estilo = db.Column(db.String(255))
    orcamento_faixa = db.Column(db.String(30))
    consent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    tipo = db.Column(db.String(30), default="consultoria_imagem")
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    status = db.Column(db.String(20), default="agendada")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StyleReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="rascunho")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default="pendente")
    due_date = db.Column(db.Date)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
