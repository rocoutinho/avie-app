from datetime import datetime

from flask import Blueprint, redirect, render_template, url_for

from emails import send_diagnostic_confirmation
from extensions import db, limiter
from forms import DiagnosticForm
from models import Client, StyleProfile

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def landing():
    return render_template("landing.html")


@public_bp.route("/privacidade")
def privacy():
    return render_template("privacy.html")


@public_bp.route("/diagnostico", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def diagnostic():
    form = DiagnosticForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        client = Client.query.filter_by(email=email).first()
        is_new = client is None
        if client is None:
            client = Client(email=email, status="lead")

        client.full_name = form.full_name.data.strip()
        client.phone = form.phone.data.strip()
        client.instagram = form.instagram.data.strip() if form.instagram.data else None
        client.source = form.source.data
        db.session.add(client)
        db.session.flush()

        profile = client.profile or StyleProfile(client_id=client.id)
        profile.objetivo_profissional = form.objetivo_profissional.data
        profile.momento_carreira = form.momento_carreira.data
        profile.como_quer_ser_percebida = form.como_quer_ser_percebida.data
        profile.desafios_imagem = form.desafios_imagem.data
        profile.ambiente_trabalho = form.ambiente_trabalho.data
        profile.estilo_atual = form.estilo_atual.data
        profile.cores_preferidas = form.cores_preferidas.data
        profile.referencias_estilo = form.referencias_estilo.data
        profile.orcamento_faixa = form.orcamento_faixa.data
        profile.consent_at = datetime.utcnow()
        db.session.add(profile)

        if not is_new and client.status == "lead":
            client.status = "diagnostico_concluido"

        db.session.commit()
        send_diagnostic_confirmation(client)
        return redirect(url_for("public.diagnostic_success"))

    return render_template("diagnostic_form.html", form=form)


@public_bp.route("/diagnostico/obrigado")
def diagnostic_success():
    return render_template("diagnostic_success.html")
