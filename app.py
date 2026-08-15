import os

import click
from flask import Flask

from config import Config
from extensions import db, login_manager
from models import (
    CLIENT_STATUSES,
    CONSULTATION_STATUSES,
    CONSULTATION_TYPES,
    PAYMENT_STATUSES,
    REPORT_STATUSES,
    User,
)


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar o painel."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from blueprints.auth import auth_bp
    from blueprints.clients import clients_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.public import public_bp
    from blueprints.reports import reports_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(reports_bp)

    @app.context_processor
    def inject_globals():
        return dict(
            CLIENT_STATUSES=CLIENT_STATUSES,
            CONSULTATION_TYPES=CONSULTATION_TYPES,
            CONSULTATION_STATUSES=CONSULTATION_STATUSES,
            REPORT_STATUSES=REPORT_STATUSES,
            PAYMENT_STATUSES=PAYMENT_STATUSES,
            label_for=lambda choices, key: dict(choices).get(key, key),
        )

    register_cli(app)
    return app


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas do banco de dados."""
        db.create_all()
        click.echo("Banco de dados inicializado.")

    @app.cli.command("create-admin")
    def create_admin():
        """Cria o primeiro usuário (staff) do sistema."""
        name = click.prompt("Nome")
        email = click.prompt("E-mail").strip().lower()
        password = click.prompt("Senha", hide_input=True, confirmation_prompt=True)

        if User.query.filter_by(email=email).first():
            click.echo("Já existe um usuário com esse e-mail.")
            return

        user = User(name=name, email=email, role="owner")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Usuário '{name}' criado com sucesso.")


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
