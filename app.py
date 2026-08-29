import logging
import os
import shutil
from datetime import datetime, timedelta
from decimal import Decimal

import click
from flask import Flask

from blog_engine import format_date_pt, render_markdown
from config import Config, IS_PRODUCTION
from extensions import db, limiter, login_manager, mail, migrate
from models import (
    BLOG_POST_STATUSES,
    CAMPAIGN_STATUSES,
    CLIENT_STATUSES,
    CONSULTATION_STATUSES,
    CONSULTATION_TYPES,
    LEAD_SOURCES,
    PAYMENT_STATUSES,
    REPORT_STATUSES,
    Client,
    Consultation,
    Payment,
    StyleReport,
    User,
)

MIN_PASSWORD_LENGTH = 10


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)
    app.logger.setLevel(logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    mail.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar o painel."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        # user_id vem prefixado por get_id() (User.get_id/Client.get_id) —
        # staff e cliente compartilham o /login mas são contas distintas.
        kind, _, raw_id = user_id.partition("-")
        if kind == "client":
            return Client.query.get(int(raw_id))
        if kind == "user":
            return User.query.get(int(raw_id))
        return None

    from blueprints.auth import auth_bp
    from blueprints.blog import blog_bp
    from blueprints.campaigns import campaigns_bp
    from blueprints.client_area import client_area_bp
    from blueprints.clients import clients_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.ebooks import ebooks_bp
    from blueprints.public import public_bp
    from blueprints.reports import reports_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(ebooks_bp)
    app.register_blueprint(client_area_bp)

    app.jinja_env.filters["markdown"] = render_markdown
    app.jinja_env.filters["pt_date"] = format_date_pt

    @app.context_processor
    def inject_globals():
        return dict(
            CLIENT_STATUSES=CLIENT_STATUSES,
            CONSULTATION_TYPES=CONSULTATION_TYPES,
            CONSULTATION_STATUSES=CONSULTATION_STATUSES,
            REPORT_STATUSES=REPORT_STATUSES,
            PAYMENT_STATUSES=PAYMENT_STATUSES,
            LEAD_SOURCES=LEAD_SOURCES,
            CAMPAIGN_STATUSES=CAMPAIGN_STATUSES,
            BLOG_POST_STATUSES=BLOG_POST_STATUSES,
            label_for=lambda choices, key: dict(choices).get(key, key),
            current_year=datetime.utcnow().year,
        )

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    register_cli(app)
    return app


def register_cli(app):
    @app.cli.command("create-admin")
    def create_admin():
        """Cria um usuário (staff) do sistema, com papel owner ou marketing."""
        name = click.prompt("Nome")
        email = click.prompt("E-mail").strip().lower()
        password = click.prompt("Senha", hide_input=True, confirmation_prompt=True)
        role = click.prompt(
            "Papel (owner = acesso total e aprova campanhas / marketing = cria e edita campanhas)",
            default="owner",
            type=click.Choice(["owner", "marketing"]),
        )

        if len(password) < MIN_PASSWORD_LENGTH:
            click.echo(f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
            return

        if User.query.filter_by(email=email).first():
            click.echo("Já existe um usuário com esse e-mail.")
            return

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Usuário '{name}' criado com sucesso (papel: {role}).")

    @app.cli.command("seed-admin")
    def seed_admin():
        """Cria o usuário admin a partir das variáveis de ambiente ADMIN_*,
        sem interação — pra rodar sozinho a cada deploy (ver startCommand
        no render.yaml). Necessário porque o disco do plano free do Render
        é efêmero: sem isso, o login some a cada deploy/restart. Não faz
        nada se ADMIN_EMAIL/ADMIN_PASSWORD não estiverem definidos, ou se
        o usuário já existir."""
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        name = os.environ.get("ADMIN_NAME", "Admin")
        role = os.environ.get("ADMIN_ROLE", "owner")

        if not email or not password:
            click.echo("ADMIN_EMAIL/ADMIN_PASSWORD não definidos — nada a fazer.")
            return

        if role not in ("owner", "marketing"):
            click.echo(f"ADMIN_ROLE inválido: '{role}' (use 'owner' ou 'marketing').")
            return

        if len(password) < MIN_PASSWORD_LENGTH:
            click.echo(f"ADMIN_PASSWORD precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
            return

        if User.query.filter_by(email=email).first():
            click.echo(f"Usuário '{email}' já existe — nada a fazer.")
            return

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Usuário '{name}' <{email}> criado (papel: {role}).")

    @app.cli.command("seed-demo-client")
    def seed_demo_client():
        """Cria (ou reseta) um cliente fictício com dados em todas as áreas
        do sistema — dossiê, relatório de acompanhamento, rascunho,
        consultorias e pagamentos — pra navegar o sistema de ponta a ponta
        sem depender de dados reais de clientes. Idempotente: identifica o
        cliente por e-mail fixo e substitui os dados de exemplo a cada
        execução, então pode ser rodado de novo quando quiser um estado
        limpo. E-mail e telefone são propositalmente fictícios (domínio
        'example.com', reservado pra isso; número que não corresponde a
        nenhum WhatsApp real) pra nunca disparar contato de verdade."""
        email = "cliente.demo@example.com"
        password = "Demo@2026!"

        client = Client.query.filter_by(email=email).first()
        if client is None:
            client = Client(email=email)
            db.session.add(client)
        client.full_name = "Ana Demonstração"
        client.phone = "11900000000"
        client.instagram = "ana.demonstracao"
        client.source = "instagram"
        client.status = "cliente_ativo"
        client.notes = (
            "Cliente fictício criado para navegação e testes internos "
            "(flask seed-demo-client) — não é um lead real."
        )
        client.utm_source = "instagram"
        client.utm_medium = "social"
        client.utm_campaign = "demo-interno"
        client.set_password(password)
        db.session.flush()

        StyleReport.query.filter_by(client_id=client.id).delete()
        Consultation.query.filter_by(client_id=client.id).delete()
        Payment.query.filter_by(client_id=client.id).delete()

        now = datetime.utcnow()
        db.session.add(
            StyleReport(
                client_id=client.id,
                title="Diagnóstico de Estilo e Posicionamento — Ana Demonstração",
                content=(
                    "Estilo pessoal\nEstilo elegante-clássico com toques contemporâneos — "
                    "peças de corte limpo, tecidos nobres e paleta neutra como base, com "
                    "um item de destaque por look.\n\n"
                    "Proporções\nSilhueta ampulheta. Valorizar a cintura marcada, evitar "
                    "volumes excessivos nos quadris e priorizar comprimentos na altura do "
                    "joelho ou abaixo.\n\n"
                    "Coloração\nPaleta de inverno — cores frias, contrastadas e saturadas "
                    "(azul-marinho, branco puro, vermelho profundo) favorecem mais que "
                    "tons terrosos.\n\n"
                    "Visagismo\nRosto oval. Óculos e acessórios com linhas retas e corte "
                    "de cabelo com repartição lateral reforçam a simetria natural do rosto."
                ),
                status="enviado",
                sent_at=now - timedelta(days=10),
                estilo_pessoal=(
                    "Estilo elegante-clássico com toques contemporâneos — peças de corte "
                    "limpo, tecidos nobres e paleta neutra como base, com um item de "
                    "destaque por look."
                ),
                proporcoes=(
                    "Silhueta ampulheta. Valorizar a cintura marcada, evitar volumes "
                    "excessivos nos quadris e priorizar comprimentos na altura do joelho "
                    "ou abaixo."
                ),
                coloracao=(
                    "Paleta de inverno — cores frias, contrastadas e saturadas "
                    "(azul-marinho, branco puro, vermelho profundo) favorecem mais que "
                    "tons terrosos."
                ),
                visagismo=(
                    "Rosto oval. Óculos e acessórios com linhas retas e corte de cabelo "
                    "com repartição lateral reforçam a simetria natural do rosto."
                ),
            )
        )
        db.session.add(
            StyleReport(
                client_id=client.id,
                title="Recomendações de guarda-roupa cápsula",
                content=(
                    "Sugestão de 12 peças-base para montar mais de 30 combinações "
                    "profissionais: blazer estruturado azul-marinho, calça de alfaiataria "
                    "preta, camisa de seda off-white, vestido tubinho vermelho, trench "
                    "coat bege, sapatos e bolsa em couro neutro. Relatório complementar "
                    "ao dossiê inicial."
                ),
                status="enviado",
                sent_at=now - timedelta(days=3),
            )
        )
        db.session.add(
            StyleReport(
                client_id=client.id,
                title="Próxima etapa — acessórios e styling para eventos",
                content=(
                    "Rascunho: mapear ocasiões de uso (eventos corporativos, jantares, "
                    "viagens) e alinhar três combinações completas com acessórios."
                ),
                status="rascunho",
            )
        )
        db.session.add(
            Consultation(
                client_id=client.id,
                tipo="consultoria_imagem",
                scheduled_at=now - timedelta(days=20),
                status="realizada",
                notes="Sessão inicial — levantamento de guarda-roupa e alinhamento de objetivos.",
            )
        )
        db.session.add(
            Consultation(
                client_id=client.id,
                tipo="manutencao",
                scheduled_at=now + timedelta(days=15),
                status="agendada",
                notes="Sessão de manutenção trimestral.",
            )
        )
        db.session.add(
            Payment(
                client_id=client.id,
                description="Consultoria de Imagem — pacote completo",
                amount=Decimal("2200.00"),
                status="pago",
                due_date=(now - timedelta(days=25)).date(),
                paid_at=now - timedelta(days=24),
            )
        )
        db.session.add(
            Payment(
                client_id=client.id,
                description="Sessão de manutenção trimestral",
                amount=Decimal("450.00"),
                status="pendente",
                due_date=(now + timedelta(days=15)).date(),
            )
        )
        db.session.commit()

        click.echo(f"Cliente fictício pronto: {email} / senha: {password}")
        click.echo(f"Ficha (staff): /painel/clientes/{client.id}")
        click.echo("Área do cliente: /minha-area (login com o e-mail/senha acima)")

    @app.cli.command("backup-db")
    def backup_db():
        """Copia o banco SQLite atual para instance/backups com timestamp."""
        db_path = os.path.join(app.instance_path, "avie.db")
        if not os.path.exists(db_path):
            click.echo(f"Banco de dados não encontrado em: {db_path}")
            return

        backups_dir = os.path.join(app.instance_path, "backups")
        os.makedirs(backups_dir, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(backups_dir, f"avie-{stamp}.db")
        shutil.copy2(db_path, dest)
        click.echo(f"Backup criado em {dest}")


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
