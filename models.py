import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

PASSWORD_RESET_TOKEN_VALID_HOURS = 72

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
    ("ebook", "Ebook (isca digital)"),
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

BLOG_POST_STATUSES = [
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

    def get_id(self):
        # Prefixado pra diferenciar de Client na mesma sessão de login (ver
        # login_manager.user_loader em app.py) — staff e cliente usam o
        # mesmo /login, mas são dois tipos de conta distintos.
        return f"user-{self.id}"

    @property
    def is_staff(self):
        # Usado em templates/base.html pra decidir qual navbar mostrar
        # (current_user pode ser User ou Client, ambos autenticáveis).
        return True


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


class BlogPost(db.Model):
    """Um artigo do blog — testado publicado em /blog antes de ser reaproveitado
    manualmente no LinkedIn da Fabiana. Mesmo fluxo de aprovação da Campaign:
    marketing cria como rascunho -> envia para revisão -> owner aprova
    (publica) ou recusa (volta pra rascunho, com um motivo opcional)."""

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    excerpt = db.Column(db.String(300), nullable=False)
    cover_image_url = db.Column(db.String(500))
    body_markdown = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(150), default="Fabiana Montemor", nullable=False)
    status = db.Column(db.String(20), default="rascunho", nullable=False)

    review_note = db.Column(db.Text)

    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


class Ebook(db.Model):
    """Isca digital: um PDF/material hospedado externamente (Google Drive,
    etc. — não é upload de arquivo, ver comentário em blueprints/ebooks.py)
    usado pra capturar leads em /ebook. Sem fluxo de aprovação (diferente
    de Campaign/BlogPost) — é um material de marketing simples, qualquer
    staff cria/edita direto. Só o Ebook com active=True (o mais recente)
    aparece na página pública."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cover_image_url = db.Column(db.String(500))
    file_url = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])


class Client(UserMixin, db.Model):
    """Além do registro de CRM, um Client pode opcionalmente logar sozinho
    (área do cliente, ver blueprints/client_area.py) — mas só se um staff
    definir uma senha de acesso pra ele (client_detail.html); sem isso
    password_hash fica None e o login como cliente nunca é possível.
    UserMixin permite o Flask-Login tratar Client como um "usuário" de
    sessão igual a User — os dois compartilham o mesmo /login (ver
    blueprints/auth.py), diferenciados por um prefixo em get_id()."""

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

    # Acesso à área do cliente (opcional — ver docstring acima).
    password_hash = db.Column(db.String(255))
    last_login_at = db.Column(db.DateTime)

    # Link de "trocar senha" enviado por e-mail/WhatsApp no cadastro com
    # dossiê (ver blueprints/clients.py:new_client_with_dossie) — permite o
    # cliente escolher a própria senha em vez de usar a temporária gerada
    # pelo sistema. Token de uso único, expira em PASSWORD_RESET_TOKEN_VALID_HOURS.
    password_reset_token = db.Column(db.String(100), unique=True)
    password_reset_expires_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    def generate_password_reset_token(self):
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_expires_at = datetime.utcnow() + timedelta(
            hours=PASSWORD_RESET_TOKEN_VALID_HOURS
        )
        return token

    def password_reset_token_valid(self):
        return bool(self.password_reset_token) and bool(self.password_reset_expires_at) and (
            datetime.utcnow() < self.password_reset_expires_at
        )

    def clear_password_reset_token(self):
        self.password_reset_token = None
        self.password_reset_expires_at = None

    def get_id(self):
        return f"client-{self.id}"

    @property
    def is_staff(self):
        return False

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
