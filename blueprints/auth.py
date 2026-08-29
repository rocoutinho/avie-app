from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db, limiter
from forms import LoginForm, ResetPasswordForm
from models import Client, User

auth_bp = Blueprint("auth", __name__)


def require_staff():
    """Bloqueia clientes (e visitantes anônimos) de entrar nas áreas
    internas (/painel/*) — staff e cliente compartilham o mesmo /login,
    então isolar por tipo de conta precisa ser explícito. Usado como
    before_request nos blueprints internos (dashboard, clients, reports,
    campaigns, blog, ebooks)."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not isinstance(current_user, User):
        abort(403)


def _post_login_redirect(user, next_page=None):
    if isinstance(user, User):
        return next_page or url_for("dashboard.index")
    return url_for("client_area.index")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect(current_user))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(_post_login_redirect(user, request.args.get("next")))

        client = Client.query.filter_by(email=email).first()
        if client and client.check_password(password):
            # Guarda o acesso anterior (se houver) antes de sobrescrever,
            # pra área do cliente conseguir mostrar "seu último acesso foi
            # em ..." uma vez só, logo depois do login.
            session["client_previous_login_at"] = (
                client.last_login_at.isoformat() if client.last_login_at else None
            )
            client.last_login_at = datetime.utcnow()
            db.session.commit()
            login_user(client)
            return redirect(_post_login_redirect(client))

        flash("E-mail ou senha inválidos.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("public.landing"))


@auth_bp.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Link enviado por e-mail/WhatsApp no cadastro com dossiê (ver
    blueprints/clients.py:new_client_with_dossie) — deixa o cliente
    escolher a própria senha em vez de usar a temporária gerada pelo
    sistema. Rota pública: a validade está no token, não em sessão."""
    if current_user.is_authenticated:
        logout_user()

    client = Client.query.filter_by(password_reset_token=token).first()
    if client is None or not client.password_reset_token_valid():
        flash("Este link de acesso expirou ou já foi usado. Peça um novo à Fabiana.", "danger")
        return redirect(url_for("auth.login"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        client.set_password(form.password.data)
        client.clear_password_reset_token()
        db.session.commit()
        flash("Senha definida com sucesso — já pode entrar.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", form=form, client=client)
