"""CRUD do material de captura (ebook) — sem fluxo de aprovação (diferente
de campanhas/blog): é um ativo de marketing simples, qualquer staff
logado cria/edita/ativa. `file_url` é sempre um link externo (Google
Drive, Dropbox etc.), nunca um upload de arquivo pelo sistema — o disco
do Render (plano free) é efêmero, um PDF salvo localmente seria apagado
no próximo deploy e quebraria a isca silenciosamente para quem já tem o
link. Ver CLAUDE.md/README para mais contexto sobre essa limitação."""

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from blueprints.auth import require_staff
from extensions import db
from forms import EbookForm
from models import Ebook

ebooks_bp = Blueprint("ebooks", __name__, url_prefix="/painel/ebooks")
ebooks_bp.before_request(require_staff)


@ebooks_bp.route("/")
@login_required
def list_ebooks():
    ebooks = Ebook.query.order_by(Ebook.created_at.desc()).all()
    return render_template("ebooks_list.html", ebooks=ebooks)


@ebooks_bp.route("/novo", methods=["GET", "POST"])
@login_required
def new_ebook():
    form = EbookForm()
    if form.validate_on_submit():
        ebook = Ebook(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            cover_image_url=(form.cover_image_url.data or "").strip() or None,
            file_url=form.file_url.data.strip(),
            active=form.active.data,
            created_by_id=current_user.id,
        )
        if ebook.active:
            Ebook.query.update({Ebook.active: False})
        db.session.add(ebook)
        db.session.commit()
        flash("Ebook salvo.", "success")
        return redirect(url_for("ebooks.list_ebooks"))
    return render_template("ebook_form.html", form=form, ebook=None)


@ebooks_bp.route("/<int:ebook_id>/editar", methods=["GET", "POST"])
@login_required
def edit_ebook(ebook_id):
    ebook = Ebook.query.get_or_404(ebook_id)
    form = EbookForm(obj=ebook)
    if form.validate_on_submit():
        ebook.title = form.title.data.strip()
        ebook.description = form.description.data.strip()
        ebook.cover_image_url = (form.cover_image_url.data or "").strip() or None
        ebook.file_url = form.file_url.data.strip()
        if form.active.data and not ebook.active:
            Ebook.query.update({Ebook.active: False})
        ebook.active = form.active.data
        db.session.commit()
        flash("Ebook atualizado.", "success")
        return redirect(url_for("ebooks.list_ebooks"))
    return render_template("ebook_form.html", form=form, ebook=ebook)


@ebooks_bp.route("/<int:ebook_id>/ativar", methods=["POST"])
@login_required
def activate_ebook(ebook_id):
    ebook = Ebook.query.get_or_404(ebook_id)
    Ebook.query.update({Ebook.active: False})
    ebook.active = True
    db.session.commit()
    flash(f'"{ebook.title}" agora é o ebook ativo em /ebook.', "success")
    return redirect(url_for("ebooks.list_ebooks"))


@ebooks_bp.route("/<int:ebook_id>/excluir", methods=["POST"])
@login_required
def delete_ebook(ebook_id):
    ebook = Ebook.query.get_or_404(ebook_id)
    db.session.delete(ebook)
    db.session.commit()
    flash("Ebook excluído.", "success")
    return redirect(url_for("ebooks.list_ebooks"))
