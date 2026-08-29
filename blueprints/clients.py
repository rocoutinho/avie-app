import re
import secrets
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from blueprints.auth import require_staff
from emails import send_client_access_email
from extensions import db
from forms import ClientDossieForm, ClientForm, ConsultationForm, EditDossieForm, PaymentForm, SetClientPasswordForm
from models import CLIENT_STATUSES, Client, Consultation, Payment, StyleReport

clients_bp = Blueprint("clients", __name__, url_prefix="/painel/clientes")
clients_bp.before_request(require_staff)


def _whatsapp_link(phone, message):
    """Monta um link wa.me pro número do próprio cliente (diferente do
    wa.me com config.WHATSAPP_NUMBER usado alhures, que é o número do
    negócio) — abre uma conversa já com o texto de acesso preenchido,
    pro admin só clicar em enviar."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    if len(digits) <= 11:
        digits = "55" + digits
    return f"https://wa.me/{digits}?text={quote(message)}"


def _dossie_services_from_form(form):
    return {
        "Estilo": (form.estilo_pessoal.data or "").strip(),
        "Biotipo": (form.proporcoes.data or "").strip(),
        "Cores": (form.coloracao.data or "").strip(),
        "Visagismo": (form.visagismo.data or "").strip(),
        "Arquétipos": (form.arquetipos.data or "").strip(),
    }


def _build_dossie_content(services):
    # Combina os serviços preenchidos num texto corrido — usado nas telas
    # que ainda mostram o relatório como bloco único (report_view.html);
    # os campos individuais são o que o card de Dossiê (client_detail.html)
    # e a área do cliente (client_area.html) usam pra montar um card por
    # serviço.
    return "\n\n".join(f"{label}\n{text}" for label, text in services.items() if text)


def _apply_dossie_services(report, services):
    report.estilo_pessoal = services["Estilo"] or None
    report.proporcoes = services["Biotipo"] or None
    report.coloracao = services["Cores"] or None
    report.visagismo = services["Visagismo"] or None
    report.arquetipos = services["Arquétipos"] or None


@clients_bp.route("/")
@login_required
def list_clients():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Client.full_name.ilike(like), Client.email.ilike(like)))
    clients = query.order_by(Client.created_at.desc()).all()
    return render_template("clients_list.html", clients=clients, q=q)


@clients_bp.route("/novo", methods=["GET", "POST"])
@login_required
def new_client():
    form = ClientForm()
    if form.validate_on_submit():
        client = Client(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data,
            instagram=form.instagram.data,
            source=form.source.data,
            status=form.status.data,
            notes=form.notes.data,
        )
        db.session.add(client)
        db.session.commit()
        flash("Cliente criado com sucesso.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("client_form.html", form=form, client=None)


@clients_bp.route("/novo-com-dossie", methods=["GET", "POST"])
@login_required
def new_client_with_dossie():
    """Onboarding consolidado pra clientes reais que já receberam o
    dossiê fora do sistema (ex: em consultorias anteriores ao Avie).
    Numa submissão só: encontra ou cria o Client (por e-mail), registra o
    dossiê como StyleReport já enviado, gera uma senha temporária de
    acesso e um link de troca de senha, e manda esse link por e-mail e/ou
    WhatsApp (clique manual do admin, mesmo padrão sem API paga usado no
    resto do sistema)."""
    form = ClientDossieForm()
    if request.method == "GET":
        form.full_name.data = request.args.get("full_name", "")
        form.email.data = request.args.get("email", "")
        form.phone.data = request.args.get("phone", "")

    if form.validate_on_submit():
        services = _dossie_services_from_form(form)
        if not any(services.values()):
            flash("Preencha pelo menos um dos serviços do dossiê.", "danger")
            return render_template("client_dossie_form.html", form=form)

        email = form.email.data.strip().lower()
        client = Client.query.filter_by(email=email).first()
        if client is None:
            client = Client(email=email, source="outro")
            db.session.add(client)
        client.full_name = form.full_name.data.strip()
        client.phone = form.phone.data.strip()
        # Quem já chega com dossiê pronto já passou pelo diagnóstico e pela
        # consultoria completa — o status reflete isso (diferente de
        # "cliente_ativo", que é pra um engajamento ainda em andamento).
        client.status = "cliente_concluido"
        db.session.flush()

        # Atualiza o dossiê existente do cliente em vez de criar um novo
        # StyleReport a cada envio — assim o card de Dossiê (admin) e os
        # cards de serviço (área do cliente) sempre leem a mesma linha,
        # e editar um lado sempre reflete no outro.
        report = client.dossie_report
        if report is None:
            report = StyleReport(client_id=client.id)
            db.session.add(report)
        report.title = form.dossie_title.data.strip()
        report.content = _build_dossie_content(services)
        report.status = "enviado"
        report.sent_at = datetime.utcnow()
        report.pdf_url = (form.pdf_url.data or "").strip() or None
        _apply_dossie_services(report, services)

        temp_password = secrets.token_urlsafe(9)
        client.set_password(temp_password)
        token = client.generate_password_reset_token()
        db.session.commit()

        reset_url = url_for("auth.reset_password", token=token, _external=True)
        email_sent = send_client_access_email(client, reset_url)
        message = (
            f"Olá, {client.full_name.split(' ')[0]}! Seu dossiê de estilo já está "
            f"disponível na sua área do cliente. Para criar sua senha de acesso, "
            f"acesse: {reset_url}"
        )
        whatsapp_link = _whatsapp_link(client.phone, message)

        flash("Cadastro concluído — envie o acesso ao cliente abaixo.", "success")
        return render_template(
            "client_dossie_success.html",
            client=client,
            reset_url=reset_url,
            whatsapp_link=whatsapp_link,
            email_sent=email_sent,
        )

    return render_template("client_dossie_form.html", form=form)


@clients_bp.route("/<int:client_id>/dossie/editar", methods=["GET", "POST"])
@login_required
def edit_dossie(client_id):
    """Edita o dossiê já existente do cliente (título, PDF, os 5 serviços)
    sem tocar em identidade/acesso — diferente de new_client_with_dossie,
    que também regenera senha temporária e reenvia o acesso. É essa a via
    normal pra corrigir/atualizar um dossiê depois do cadastro inicial."""
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)

    form = EditDossieForm(obj=report)
    if request.method == "GET":
        form.dossie_title.data = report.title

    if form.validate_on_submit():
        services = _dossie_services_from_form(form)
        if not any(services.values()):
            flash("Preencha pelo menos um dos serviços do dossiê.", "danger")
            return render_template("client_dossie_edit.html", form=form, client=client)

        report.title = form.dossie_title.data.strip()
        report.pdf_url = (form.pdf_url.data or "").strip() or None
        _apply_dossie_services(report, services)
        report.content = _build_dossie_content(services)
        db.session.commit()
        flash("Dossiê atualizado.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))

    return render_template("client_dossie_edit.html", form=form, client=client)


@clients_bp.route("/<int:client_id>")
@login_required
def detail(client_id):
    client = Client.query.get_or_404(client_id)
    password_form = SetClientPasswordForm()
    return render_template("client_detail.html", client=client, password_form=password_form)


@clients_bp.route("/<int:client_id>/editar", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    form = ClientForm(obj=client)
    if form.validate_on_submit():
        client.full_name = form.full_name.data.strip()
        client.email = form.email.data.strip().lower()
        client.phone = form.phone.data
        client.instagram = form.instagram.data
        client.source = form.source.data
        client.status = form.status.data
        client.notes = form.notes.data
        db.session.commit()
        flash("Dados atualizados.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("client_form.html", form=form, client=client)


@clients_bp.route("/<int:client_id>/senha", methods=["POST"])
@login_required
def set_client_password(client_id):
    client = Client.query.get_or_404(client_id)
    form = SetClientPasswordForm()
    if form.validate_on_submit():
        client.set_password(form.password.data)
        db.session.commit()
        flash("Senha de acesso definida — repasse pro cliente por WhatsApp ou e-mail.", "success")
    else:
        flash("Não foi possível definir a senha (mínimo 8 caracteres).", "danger")
    return redirect(url_for("clients.detail", client_id=client.id))


@clients_bp.route("/<int:client_id>/senha/remover", methods=["POST"])
@login_required
def remove_client_password(client_id):
    client = Client.query.get_or_404(client_id)
    client.password_hash = None
    db.session.commit()
    flash("Acesso do cliente à área dele foi removido.", "success")
    return redirect(url_for("clients.detail", client_id=client.id))


@clients_bp.route("/<int:client_id>/status", methods=["POST"])
@login_required
def update_status(client_id):
    client = Client.query.get_or_404(client_id)
    new_status = request.form.get("status")
    if new_status in dict(CLIENT_STATUSES):
        client.status = new_status
        db.session.commit()
        flash("Status atualizado.", "success")
    return redirect(url_for("clients.detail", client_id=client.id))


@clients_bp.route("/<int:client_id>/consultas/nova", methods=["GET", "POST"])
@login_required
def new_consultation(client_id):
    client = Client.query.get_or_404(client_id)
    form = ConsultationForm()
    if form.validate_on_submit():
        consultation = Consultation(
            client_id=client.id,
            tipo=form.tipo.data,
            scheduled_at=form.scheduled_at.data,
            duration_minutes=form.duration_minutes.data,
            status=form.status.data,
            notes=form.notes.data,
        )
        db.session.add(consultation)
        if client.status in ("lead", "contatado"):
            client.status = "diagnostico_agendado"
        db.session.commit()
        flash("Consulta agendada.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("consultation_form.html", form=form, client=client)


@clients_bp.route("/<int:client_id>/pagamentos/novo", methods=["GET", "POST"])
@login_required
def new_payment(client_id):
    client = Client.query.get_or_404(client_id)
    form = PaymentForm()
    if form.validate_on_submit():
        payment = Payment(
            client_id=client.id,
            description=form.description.data.strip(),
            amount=form.amount.data,
            status=form.status.data,
            due_date=form.due_date.data,
        )
        db.session.add(payment)
        db.session.commit()
        flash("Pagamento registrado.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return render_template("payment_form.html", form=form, client=client)
