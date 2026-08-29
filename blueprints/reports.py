from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from blueprints.auth import require_staff
from extensions import db
from forms import ReportForm
from models import Client, StyleReport
from reports_engine import generate_report_draft

reports_bp = Blueprint("reports", __name__, url_prefix="/painel/clientes/<int:client_id>/relatorios")
reports_bp.before_request(require_staff)


@reports_bp.route("/novo", methods=["GET", "POST"])
@login_required
def new_report(client_id):
    """Gera o diagnóstico preliminar — o rascunho automático a partir do
    diagnóstico público (StyleProfile), pensado originalmente pra captar o
    lead. Não é pra registrar o dossiê da consultoria: isso tem seu
    próprio fluxo (ver blueprints/clients.py:new_client_with_dossie/edit_dossie)."""
    client = Client.query.get_or_404(client_id)
    form = ReportForm()

    if request.method == "GET":
        form.title.data = f"Diagnóstico preliminar — {client.full_name}"
        form.content.data = generate_report_draft(client, client.profile)

    if form.validate_on_submit():
        report = StyleReport(
            client_id=client.id,
            title=form.title.data.strip(),
            content=form.content.data,
            status=form.status.data,
        )
        if report.status == "enviado":
            report.sent_at = datetime.utcnow()
        db.session.add(report)
        if client.status in ("lead", "contatado", "diagnostico_agendado", "diagnostico_concluido"):
            client.status = "proposta_enviada"
        db.session.commit()
        flash("Relatório salvo.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))

    return render_template("report_form.html", form=form, client=client, report=None)


@reports_bp.route("/<int:report_id>")
@login_required
def view_report(client_id, report_id):
    client = Client.query.get_or_404(client_id)
    report = StyleReport.query.filter_by(id=report_id, client_id=client.id).first_or_404()
    return render_template("report_view.html", client=client, report=report)


@reports_bp.route("/<int:report_id>/editar", methods=["GET", "POST"])
@login_required
def edit_report(client_id, report_id):
    client = Client.query.get_or_404(client_id)
    report = StyleReport.query.filter_by(id=report_id, client_id=client.id).first_or_404()
    if report.is_dossie:
        # O dossiê tem seu próprio formulário estruturado (os 5 serviços +
        # PDF) — editar aqui só mexeria em `content`, deixando os campos
        # de serviço (e portanto a área do cliente) desatualizados.
        return redirect(url_for("clients.edit_dossie", client_id=client.id))
    form = ReportForm(obj=report)

    if form.validate_on_submit():
        report.title = form.title.data.strip()
        report.content = form.content.data
        was_sent = report.status == "enviado"
        report.status = form.status.data
        if report.status == "enviado" and not was_sent:
            report.sent_at = datetime.utcnow()
        db.session.commit()
        flash("Relatório atualizado.", "success")
        return redirect(url_for("reports.view_report", client_id=client.id, report_id=report.id))

    return render_template("report_form.html", form=form, client=client, report=report)


@reports_bp.route("/<int:report_id>/excluir", methods=["POST"])
@login_required
def delete_report(client_id, report_id):
    client = Client.query.get_or_404(client_id)
    report = StyleReport.query.filter_by(id=report_id, client_id=client.id).first_or_404()
    if report.is_dossie:
        abort(400)
    db.session.delete(report)
    db.session.commit()
    flash("Relatório excluído.", "success")
    return redirect(url_for("clients.detail", client_id=client.id))
