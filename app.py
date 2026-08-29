import logging
import os
import shutil
from datetime import datetime

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
