import logging
import os
import shutil
from datetime import datetime

import click
from flask import Flask

from config import Config, IS_PRODUCTION
from extensions import db, limiter, login_manager, mail, migrate
from models import (
    CAMPAIGN_STATUSES,
    CLIENT_STATUSES,
    CONSULTATION_STATUSES,
    CONSULTATION_TYPES,
    LEAD_SOURCES,
    PAYMENT_STATUSES,
    REPORT_STATUSES,
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
        return User.query.get(int(user_id))

    from blueprints.auth import auth_bp
    from blueprints.campaigns import campaigns_bp
    from blueprints.clients import clients_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.public import public_bp
    from blueprints.reports import reports_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(campaigns_bp)

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
