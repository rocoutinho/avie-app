import re
import secrets
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from blueprints.auth import require_staff
from blueprints.client_area import DOSSIE_SERVICE_LABELS
from emails import send_client_access_email
from extensions import db
from image_upload import upload_image
from forms import (
    ClientDossieForm,
    ClientForm,
    ClosetItemForm,
    ColoracaoImageForm,
    ConsultationForm,
    DossieSectionForm,
    EditDossieForm,
    LookForm,
    PaymentForm,
    SetClientPasswordForm,
    ShoppingListItemForm,
    StyleAssessmentForm,
)
from models import (
    CLIENT_STATUSES,
    CONSULTATION_STATUSES,
    CONSULTATION_TYPES,
    PERSONAL_SHOPPER_STATUSES,
    Client,
    ClosetItem,
    ColoracaoImage,
    Consultation,
    DossieSection,
    Look,
    LookItem,
    Payment,
    ShoppingListItem,
    StyleAssessment,
    StyleReport,
)

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
        "Coloração": (form.coloracao.data or "").strip(),
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
    report.coloracao = services["Coloração"] or None
    report.visagismo = services["Visagismo"] or None
    report.arquetipos = services["Arquétipos"] or None


_JOURNEY_STEP_LABELS = ["Diagnóstico", "Dossiê", "Looks", "Closet", "Personal Shopper", "Dados pessoais"]


def _next_incomplete_step_label(client):
    """Mesma lógica de preenchimento usada pelo dot-tracker de
    client_detail.html (timeline_steps), só que sem os hrefs — usada aqui
    pra dar um rótulo de "próxima ação" na listagem quando não há consulta
    futura agendada. Duplicada de propósito (booleans simples, baixo risco
    de divergir) em vez de fazer o template de detail depender de Python
    pra algo que já funciona lá."""
    has_personal_data = bool(
        client.notes
        or client.style_notes
        or client.identidade_rotina
        or client.identidade_objetivo
        or client.identidade_estilo
        or client.idade
        or client.profissao
        or client.cidade
    )
    filled = [
        bool(client.profile or client.style_assessment or client.other_reports),
        client.dossie_report is not None,
        len(client.looks) > 0,
        len(client.closet_items) > 0,
        len(client.shopping_list_items) > 0,
        bool(has_personal_data or client.password_hash),
    ]
    for label, is_filled in zip(_JOURNEY_STEP_LABELS, filled):
        if not is_filled:
            return label
    return None


def _next_action_for_client(client, now):
    """Próxima ação mostrada na listagem: uma consulta futura já agendada
    (o dado mais concreto que existe) ou, na falta dela, a próxima etapa da
    jornada ainda sem conteúdo. Nunca inventa uma ação — só lê o que já
    está no cadastro."""
    upcoming = [c for c in client.consultations if c.status == "agendada" and c.scheduled_at >= now]
    if upcoming:
        next_consultation = min(upcoming, key=lambda c: c.scheduled_at)
        tipo_label = dict(CONSULTATION_TYPES).get(next_consultation.tipo, next_consultation.tipo)
        return f"{tipo_label} · {next_consultation.scheduled_at.strftime('%d/%m')}"
    step = _next_incomplete_step_label(client)
    if step:
        return f"Completar {step}"
    return None


@clients_bp.route("/")
@login_required
def list_clients():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Client.full_name.ilike(like), Client.email.ilike(like)))
    clients = query.order_by(Client.created_at.desc()).all()
    now = datetime.utcnow()
    next_actions = {c.id: _next_action_for_client(c, now) for c in clients}
    return render_template("clients_list.html", clients=clients, q=q, next_actions=next_actions)


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
            style_notes=form.style_notes.data,
            idade=form.idade.data,
            profissao=form.profissao.data,
            cidade=form.cidade.data,
            foto_perfil=upload_image(form.foto_perfil_arquivo.data) or form.foto_perfil.data,
            identidade_rotina=form.identidade_rotina.data,
            identidade_objetivo=form.identidade_objetivo.data,
            identidade_estilo=form.identidade_estilo.data,
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
        return redirect(url_for("clients.dossie", client_id=client.id))

    return render_template("client_dossie_edit.html", form=form, client=client)


def _next_action_banner(client, now):
    """Igual a _next_action_for_client, mas devolve título + prazo
    separados pra faixa de destaque do hub (client_detail.html), em vez de
    uma única string pra célula de tabela."""
    upcoming = [c for c in client.consultations if c.status == "agendada" and c.scheduled_at >= now]
    if upcoming:
        next_consultation = min(upcoming, key=lambda c: c.scheduled_at)
        tipo_label = dict(CONSULTATION_TYPES).get(next_consultation.tipo, next_consultation.tipo)
        return {
            "title": f"Preparar {tipo_label}",
            "deadline": next_consultation.scheduled_at.strftime("%d/%m, %H:%M"),
        }
    step = _next_incomplete_step_label(client)
    if step:
        return {"title": f"Completar {step}", "deadline": None}
    return None


def _client_timeline(client):
    """Linha do tempo unificada de client_detail.html — eventos reais de
    Consulta/Pagamento/Dossiê/acesso ao portal/diagnóstico público, cada um
    com a etiqueta de onde nasceu (Admin/Portal). Não existe um log de
    canal de atendimento (WhatsApp/presencial) no banco, então a etiqueta
    reflete só isso: quem gerou o registro, staff ou a própria cliente pelo
    portal — não o meio de conversa usado. Ver CLAUDE.md."""
    events = []
    if client.created_at:
        events.append({"time": client.created_at, "text": "Cliente cadastrada", "channel": "Admin"})
    if client.profile and client.profile.created_at:
        events.append(
            {"time": client.profile.created_at, "text": "Diagnóstico público preenchido", "channel": "Portal"}
        )
    for con in client.consultations:
        tipo_label = dict(CONSULTATION_TYPES).get(con.tipo, con.tipo)
        status_label = dict(CONSULTATION_STATUSES).get(con.status, con.status)
        events.append({"time": con.scheduled_at, "text": f"{tipo_label} — {status_label}", "channel": "Admin"})
    for p in client.payments:
        if p.created_at:
            events.append({"time": p.created_at, "text": f"Cobrança registrada: {p.description}", "channel": "Admin"})
        if p.paid_at:
            events.append({"time": p.paid_at, "text": f"Pagamento recebido: {p.description}", "channel": "Admin"})
    dossie = client.dossie_report
    if dossie:
        if dossie.sent_at:
            events.append({"time": dossie.sent_at, "text": "Dossiê enviado", "channel": "Admin"})
        elif dossie.created_at:
            events.append({"time": dossie.created_at, "text": "Dossiê criado", "channel": "Admin"})
    if client.last_login_at:
        events.append({"time": client.last_login_at, "text": "Acessou a área da cliente", "channel": "Portal"})

    events.sort(key=lambda e: e["time"], reverse=True)
    return events[:10]


@clients_bp.route("/<int:client_id>")
@login_required
def detail(client_id):
    """Hub da cliente — cabeçalho + ações rápidas + jornada + próxima ação
    em destaque + linha do tempo unificada, seguida da grade de cards da
    jornada (Diagnóstico, Dossiê, Looks, Closet, Personal Shopper, Dados
    pessoais), cada um levando pra sua própria tela de detalhe. Consultas e
    Pagamentos continuam aqui direto (são dado operacional/financeiro, não
    uma etapa da jornada de estilo)."""
    client = Client.query.get_or_404(client_id)
    contact_message = f"Olá, {client.full_name.split(' ')[0]}!"
    whatsapp_link = _whatsapp_link(client.phone, contact_message) if client.phone else None
    now = datetime.utcnow()
    return render_template(
        "client_detail.html",
        client=client,
        whatsapp_link=whatsapp_link,
        next_action=_next_action_banner(client, now),
        timeline=_client_timeline(client),
    )


@clients_bp.route("/<int:client_id>/diagnostico")
@login_required
def diagnostico(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template("client_diagnostico.html", client=client)


@clients_bp.route("/<int:client_id>/dossie")
@login_required
def dossie(client_id):
    """Hub dos 5 serviços do dossiê (Estilo/Biotipo/Coloração/Visagismo/
    Arquétipos), cada um seu próprio card — mesmo padrão .journey-grid/
    .journey-card já usado nos outros hubs (client_detail.html, área da
    cliente). Coloração é o único serviço com página própria mais rica
    (texto + galeria de imagens, ver dossie_coloracao); os outros 4 caem
    em dossie_service, uma página genérica de texto."""
    client = Client.query.get_or_404(client_id)
    return render_template("client_dossie.html", client=client, DOSSIE_SERVICE_LABELS=DOSSIE_SERVICE_LABELS)


@clients_bp.route("/<int:client_id>/dossie/<service_field>")
@login_required
def dossie_service(client_id, service_field):
    valid_fields = {field for field, _label, _icon in DOSSIE_SERVICE_LABELS if field != "coloracao"}
    if service_field not in valid_fields:
        abort(404)
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    label = next(label for field, label, _icon in DOSSIE_SERVICE_LABELS if field == service_field)
    return render_template(
        "client_dossie_service.html",
        client=client,
        label=label,
        service_field=service_field,
        text=getattr(report, service_field, None),
        sections=[s for s in report.dossie_sections if s.service == service_field],
    )


@clients_bp.route("/<int:client_id>/dossie/coloracao")
@login_required
def dossie_coloracao(client_id):
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    return render_template(
        "client_dossie_coloracao.html",
        client=client,
        report=report,
        form=ColoracaoImageForm(),
        sections=[s for s in report.dossie_sections if s.service == "coloracao"],
    )


@clients_bp.route("/<int:client_id>/dossie/coloracao/imagens/nova", methods=["POST"])
@login_required
def new_coloracao_image(client_id):
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    form = ColoracaoImageForm()
    if form.validate_on_submit():
        image_url = upload_image(form.image_file.data) or form.image_url.data
        if not image_url:
            flash("Informe um link ou envie um arquivo de imagem.", "danger")
        else:
            db.session.add(ColoracaoImage(style_report_id=report.id, image_url=image_url, caption=form.caption.data))
            db.session.commit()
            flash("Imagem adicionada.", "success")
    return redirect(url_for("clients.dossie_coloracao", client_id=client.id))


@clients_bp.route("/<int:client_id>/dossie/coloracao/imagens/<int:image_id>/excluir", methods=["POST"])
@login_required
def delete_coloracao_image(client_id, image_id):
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    image = ColoracaoImage.query.filter_by(id=image_id, style_report_id=report.id).first_or_404()
    db.session.delete(image)
    db.session.commit()
    flash("Imagem removida.", "success")
    return redirect(url_for("clients.dossie_coloracao", client_id=client.id))


def _dossie_section_redirect(client_id, service_field):
    """Cada serviço tem sua própria página (dossie_service genérica, ou
    dossie_coloracao pro único serviço com página própria mais rica) —
    depois de criar/editar/excluir uma seção, volta pra página de onde
    ela veio."""
    if service_field == "coloracao":
        return redirect(url_for("clients.dossie_coloracao", client_id=client_id))
    return redirect(url_for("clients.dossie_service", client_id=client_id, service_field=service_field))


@clients_bp.route("/<int:client_id>/dossie/<service_field>/secoes/nova", methods=["GET", "POST"])
@login_required
def new_dossie_section(client_id, service_field):
    valid_fields = {field for field, _label, _icon in DOSSIE_SERVICE_LABELS}
    if service_field not in valid_fields:
        abort(404)
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    label = next(label for field, label, _icon in DOSSIE_SERVICE_LABELS if field == service_field)
    form = DossieSectionForm()
    if form.validate_on_submit():
        section = DossieSection(
            style_report_id=report.id,
            service=service_field,
            title=form.title.data.strip(),
            content=form.content.data,
            image_url=upload_image(form.image_file.data) or form.image_url.data,
            group=form.group.data or None,
            order=form.order.data or 0,
        )
        db.session.add(section)
        db.session.commit()
        flash("Seção adicionada.", "success")
        return _dossie_section_redirect(client.id, service_field)
    return render_template("dossie_section_form.html", form=form, client=client, label=label, section=None)


@clients_bp.route("/<int:client_id>/dossie/secoes/<int:section_id>/editar", methods=["GET", "POST"])
@login_required
def edit_dossie_section(client_id, section_id):
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    section = DossieSection.query.filter_by(id=section_id, style_report_id=report.id).first_or_404()
    label = next(label for field, label, _icon in DOSSIE_SERVICE_LABELS if field == section.service)
    form = DossieSectionForm(obj=section)
    if form.validate_on_submit():
        section.title = form.title.data.strip()
        section.content = form.content.data
        section.image_url = upload_image(form.image_file.data) or form.image_url.data
        section.group = form.group.data or None
        section.order = form.order.data or 0
        db.session.commit()
        flash("Seção atualizada.", "success")
        return _dossie_section_redirect(client.id, section.service)
    return render_template("dossie_section_form.html", form=form, client=client, label=label, section=section)


@clients_bp.route("/<int:client_id>/dossie/secoes/<int:section_id>/excluir", methods=["POST"])
@login_required
def delete_dossie_section(client_id, section_id):
    client = Client.query.get_or_404(client_id)
    report = client.dossie_report
    if report is None:
        abort(404)
    section = DossieSection.query.filter_by(id=section_id, style_report_id=report.id).first_or_404()
    service_field = section.service
    db.session.delete(section)
    db.session.commit()
    flash("Seção removida.", "success")
    return _dossie_section_redirect(client.id, service_field)


@clients_bp.route("/<int:client_id>/looks")
@login_required
def looks(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template("client_looks.html", client=client)


@clients_bp.route("/<int:client_id>/closet")
@login_required
def closet(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template("client_closet.html", client=client)


@clients_bp.route("/<int:client_id>/lista-compras")
@login_required
def personal_shopper(client_id):
    client = Client.query.get_or_404(client_id)
    # Link pra consultora avisar a cliente que tem uma recomendação com link
    # de compra pronta — mesmo padrão de _whatsapp_link usado no resto do
    # hub, mas por item (só faz sentido pra quem já tem link_compra).
    whatsapp_links = {
        item.id: _whatsapp_link(
            client.phone,
            f"Olá, {client.full_name.split(' ')[0]}! Separei uma recomendação de compra pra você: "
            f"{item.description} — {item.link_compra}",
        )
        for item in client.shopping_list_items
        if item.link_compra
    }
    return render_template("client_personal_shopper.html", client=client, whatsapp_links=whatsapp_links)


@clients_bp.route("/<int:client_id>/dados-pessoais")
@login_required
def dados_pessoais(client_id):
    client = Client.query.get_or_404(client_id)
    password_form = SetClientPasswordForm()
    return render_template("client_dados_pessoais.html", client=client, password_form=password_form)


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
        client.style_notes = form.style_notes.data
        client.idade = form.idade.data
        client.profissao = form.profissao.data
        client.cidade = form.cidade.data
        client.foto_perfil = upload_image(form.foto_perfil_arquivo.data) or form.foto_perfil.data
        client.identidade_rotina = form.identidade_rotina.data
        client.identidade_objetivo = form.identidade_objetivo.data
        client.identidade_estilo = form.identidade_estilo.data
        client.foco_atual = form.foco_atual.data
        db.session.commit()
        flash("Dados atualizados.", "success")
        return redirect(url_for("clients.dados_pessoais", client_id=client.id))
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
    return redirect(url_for("clients.dados_pessoais", client_id=client.id))


@clients_bp.route("/<int:client_id>/senha/remover", methods=["POST"])
@login_required
def remove_client_password(client_id):
    client = Client.query.get_or_404(client_id)
    client.password_hash = None
    db.session.commit()
    flash("Acesso do cliente à área dele foi removido.", "success")
    return redirect(url_for("clients.dados_pessoais", client_id=client.id))


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


@clients_bp.route("/<int:client_id>/closet/novo", methods=["GET", "POST"])
@login_required
def new_closet_item(client_id):
    client = Client.query.get_or_404(client_id)
    form = ClosetItemForm()
    if form.validate_on_submit():
        item = ClosetItem(
            client_id=client.id,
            category=form.category.data,
            description=form.description.data.strip(),
            photo_url=upload_image(form.photo_file.data) or form.photo_url.data,
            notes=form.notes.data,
        )
        db.session.add(item)
        db.session.commit()
        flash("Peça adicionada ao closet.", "success")
        return redirect(url_for("clients.closet", client_id=client.id))
    return render_template("closet_item_form.html", form=form, client=client)


@clients_bp.route("/<int:client_id>/closet/<int:item_id>/excluir", methods=["POST"])
@login_required
def delete_closet_item(client_id, item_id):
    client = Client.query.get_or_404(client_id)
    item = ClosetItem.query.filter_by(id=item_id, client_id=client.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Peça removida do closet.", "success")
    return redirect(url_for("clients.closet", client_id=client.id))


@clients_bp.route("/<int:client_id>/lista-compras/novo", methods=["GET", "POST"])
@login_required
def new_shopping_list_item(client_id):
    client = Client.query.get_or_404(client_id)
    form = ShoppingListItemForm()
    if form.validate_on_submit():
        item = ShoppingListItem(
            client_id=client.id,
            category=form.category.data,
            description=form.description.data.strip(),
            motivo=form.motivo.data,
            photo_url=upload_image(form.photo_file.data) or form.photo_url.data,
            link_compra=form.link_compra.data,
            notes=form.notes.data,
        )
        db.session.add(item)
        db.session.commit()
        flash("Recomendação adicionada.", "success")
        return redirect(url_for("clients.personal_shopper", client_id=client.id))
    return render_template("shopping_list_item_form.html", form=form, client=client)


@clients_bp.route("/<int:client_id>/lista-compras/<int:item_id>/editar", methods=["GET", "POST"])
@login_required
def edit_shopping_list_item(client_id, item_id):
    client = Client.query.get_or_404(client_id)
    item = ShoppingListItem.query.filter_by(id=item_id, client_id=client.id).first_or_404()
    form = ShoppingListItemForm(obj=item)
    if form.validate_on_submit():
        item.category = form.category.data
        item.description = form.description.data.strip()
        item.motivo = form.motivo.data
        item.photo_url = upload_image(form.photo_file.data) or form.photo_url.data
        item.link_compra = form.link_compra.data
        item.notes = form.notes.data
        db.session.commit()
        flash("Recomendação atualizada.", "success")
        return redirect(url_for("clients.personal_shopper", client_id=client.id))
    return render_template("shopping_list_item_form.html", form=form, client=client, item=item)


@clients_bp.route("/<int:client_id>/lista-compras/<int:item_id>/status", methods=["POST"])
@login_required
def set_shopping_list_item_status(client_id, item_id):
    client = Client.query.get_or_404(client_id)
    item = ShoppingListItem.query.filter_by(id=item_id, client_id=client.id).first_or_404()
    status = request.form.get("status")
    if status in dict(PERSONAL_SHOPPER_STATUSES):
        item.status = status
        db.session.commit()
    return redirect(url_for("clients.personal_shopper", client_id=client.id))


@clients_bp.route("/<int:client_id>/lista-compras/<int:item_id>/excluir", methods=["POST"])
@login_required
def delete_shopping_list_item(client_id, item_id):
    client = Client.query.get_or_404(client_id)
    item = ShoppingListItem.query.filter_by(id=item_id, client_id=client.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Peça removida da lista de compras.", "success")
    return redirect(url_for("clients.personal_shopper", client_id=client.id))


@clients_bp.route("/<int:client_id>/looks/novo", methods=["GET", "POST"])
@login_required
def new_look(client_id):
    client = Client.query.get_or_404(client_id)
    form = LookForm()
    form.closet_item_ids.choices = [(item.id, item.description) for item in client.closet_items]
    if form.validate_on_submit():
        look = Look(
            client_id=client.id,
            nome=form.nome.data.strip(),
            photo_url=upload_image(form.photo_file.data) or form.photo_url.data,
            momento=form.momento.data,
            ocasiao=form.ocasiao.data,
            descricao=form.descricao.data,
            mensagem_transmitida=form.mensagem_transmitida.data,
        )
        for closet_item_id in form.closet_item_ids.data:
            look.items.append(LookItem(closet_item_id=closet_item_id))
        db.session.add(look)
        db.session.commit()
        flash("Look criado.", "success")
        return redirect(url_for("clients.looks", client_id=client.id))
    return render_template("look_form.html", form=form, client=client)


@clients_bp.route("/<int:client_id>/looks/<int:look_id>/excluir", methods=["POST"])
@login_required
def delete_look(client_id, look_id):
    client = Client.query.get_or_404(client_id)
    look = Look.query.filter_by(id=look_id, client_id=client.id).first_or_404()
    db.session.delete(look)
    db.session.commit()
    flash("Look removido.", "success")
    return redirect(url_for("clients.looks", client_id=client.id))


@clients_bp.route("/<int:client_id>/diagnostico-estruturado/editar", methods=["GET", "POST"])
@login_required
def edit_style_assessment(client_id):
    """Cria ou edita o StyleAssessment do cliente — 1 registro por cliente,
    mesmo padrão 1:1 de edit_dossie, mas aqui a primeira submissão já cria o
    registro (não existe rota separada de "novo")."""
    client = Client.query.get_or_404(client_id)
    assessment = client.style_assessment
    form = StyleAssessmentForm(obj=assessment)
    if form.validate_on_submit():
        if assessment is None:
            assessment = StyleAssessment(client_id=client.id)
            db.session.add(assessment)
        assessment.estacao_cor = form.estacao_cor.data
        assessment.paleta_principal = form.paleta_principal.data
        assessment.estilo_predominante = form.estilo_predominante.data
        assessment.estilo_complementar = form.estilo_complementar.data
        assessment.mensagem_desejada = form.mensagem_desejada.data
        assessment.pontos_chave = form.pontos_chave.data
        db.session.commit()
        flash("Diagnóstico estruturado atualizado.", "success")
        return redirect(url_for("clients.diagnostico", client_id=client.id))
    return render_template("style_assessment_form.html", form=form, client=client)
