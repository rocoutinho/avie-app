from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from forms import ClientForm, ConsultationForm, PaymentForm
from models import CLIENT_STATUSES, Client, Consultation, Payment

clients_bp = Blueprint("clients", __name__, url_prefix="/painel/clientes")


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


@clients_bp.route("/<int:client_id>")
@login_required
def detail(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template("client_detail.html", client=client)


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
