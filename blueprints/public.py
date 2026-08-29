import os
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_wtf.csrf import ValidationError, validate_csrf

from emails import send_diagnostic_confirmation
from extensions import db, limiter
from forms import DiagnosticForm
from models import LEAD_SOURCES, BlogPost, Campaign, Client, StyleProfile

public_bp = Blueprint("public", __name__)

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

# Mapeia utm_source (valor livre, definido em cada link de campanha) para as
# opções fechadas de LEAD_SOURCES, usado só para sugerir um valor no
# dropdown "Como você conheceu o trabalho?" — a pessoa pode sempre corrigir.
UTM_SOURCE_TO_LEAD_SOURCE = {
    "instagram": "instagram",
    "ig": "instagram",
    "facebook": "instagram",
    "fb": "instagram",
    "meta": "instagram",
    "google": "google",
    "google_ads": "google",
    "adwords": "google",
    "linkedin": "linkedin",
}


@public_bp.before_request
def capture_campaign_attribution():
    """Guarda utm_* (e a origem provável) na sessão na primeira visita com
    parâmetros de campanha — funciona tanto para quem chega pela landing
    quanto para quem clica direto num link para /diagnostico."""
    has_utm = any(key in request.args for key in UTM_KEYS)
    has_click_id = "gclid" in request.args or "fbclid" in request.args
    if not (has_utm or has_click_id):
        return

    for key in UTM_KEYS:
        if key in request.args:
            session[key] = request.args.get(key, "").strip()[:150]

    utm_source = (request.args.get("utm_source") or "").strip().lower()
    if not utm_source:
        if "gclid" in request.args:
            utm_source = "google"
        elif "fbclid" in request.args:
            utm_source = "instagram"
        if utm_source:
            session["utm_source"] = utm_source

    lead_source = UTM_SOURCE_TO_LEAD_SOURCE.get(utm_source)
    if lead_source:
        session["lead_source_guess"] = lead_source


@public_bp.route("/favicon.ico")
def favicon():
    # Navegadores e crawlers pedem esse caminho por convenção, independente
    # da tag <link rel="icon"> no <head>.
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@public_bp.route("/")
def landing():
    return render_template("landing.html")


@public_bp.route("/lp/<slug>")
def landing_campaign(slug):
    campaign = Campaign.query.filter_by(slug=slug, status="publicado").first_or_404()
    # Se a visita não trouxe utm_campaign explícito (ex: link direto pro
    # criativo), usa o slug como atribuição — assim os leads dessa página
    # ficam rastreados até essa campanha mesmo sem parâmetros na URL.
    if "utm_campaign" not in session and "utm_campaign" not in request.args:
        session["utm_campaign"] = campaign.slug
    return render_template("landing.html", campaign=campaign)


@public_bp.route("/privacidade")
def privacy():
    return render_template("privacy.html")


@public_bp.route("/blog")
def blog_index():
    posts = BlogPost.query.filter_by(status="publicado").order_by(BlogPost.published_at.desc()).all()
    return render_template("blog_list.html", posts=posts)


@public_bp.route("/blog/<slug>")
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, status="publicado").first_or_404()
    return render_template("blog_post.html", post=post)


@public_bp.route("/diagnostico", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def diagnostic():
    form = DiagnosticForm()

    if request.method == "GET":
        for key in UTM_KEYS:
            getattr(form, key).data = session.get(key, "")
        if session.get("lead_source_guess"):
            form.source.data = session["lead_source_guess"]

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
        _apply_utm(client, form)
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


def _apply_utm(client, source):
    """Copia utm_* de um form ou dict para o Client, sem apagar valores já
    salvos quando o campo novo vier vazio."""
    get = source.get if isinstance(source, dict) else lambda k: getattr(source, k).data
    for key in UTM_KEYS:
        value = (get(key) or "").strip()
        if value:
            setattr(client, key, value[:150])


@public_bp.route("/diagnostico/lead-parcial", methods=["POST"])
@limiter.limit("15 per hour")
def diagnostic_partial_lead():
    """Salva um lead de contato mínimo assim que a pessoa termina a etapa 1
    do wizard (nome, e-mail, telefone) — antes de ela decidir se continua
    até o fim. Sem isso, quem preenche a etapa 1 e abandona o formulário
    (comum em tráfego pago frio) não vira nem um contato na equipe seguir.
    Não salva nenhum dado sensível do diagnóstico (isso só acontece no
    envio completo, com consentimento explícito)."""
    data = request.get_json(silent=True) or {}

    if current_app.config.get("WTF_CSRF_ENABLED", True):
        try:
            validate_csrf(data.get("csrf_token", ""))
        except ValidationError:
            return jsonify(ok=False), 400

    full_name = (data.get("full_name") or "").strip()[:150]
    email = (data.get("email") or "").strip().lower()[:150]
    if not full_name or not email or "@" not in email:
        return jsonify(ok=False), 400

    client = Client.query.filter_by(email=email).first()
    if client is None:
        client = Client(email=email, status="lead")

    client.full_name = full_name
    phone = (data.get("phone") or "").strip()[:30]
    if phone:
        client.phone = phone
    instagram = (data.get("instagram") or "").strip()[:100]
    if instagram:
        client.instagram = instagram
    source = data.get("source")
    if source in dict(LEAD_SOURCES):
        client.source = source
    _apply_utm(client, data)

    db.session.add(client)
    db.session.commit()
    return jsonify(ok=True)
