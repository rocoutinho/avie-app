from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints.auth import require_staff
from extensions import db
from forms import CampaignForm, CampaignReviewForm
from models import Campaign

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/painel/campanhas")
campaigns_bp.before_request(require_staff)


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user.role != "owner":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@campaigns_bp.route("/")
@login_required
def list_campaigns():
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    return render_template("campaigns_list.html", campaigns=campaigns)


@campaigns_bp.route("/novo", methods=["GET", "POST"])
@login_required
def new_campaign():
    form = CampaignForm()
    if form.validate_on_submit():
        slug = form.slug.data.strip().lower()
        if Campaign.query.filter_by(slug=slug).first():
            flash("Já existe um criativo com esse slug.", "danger")
            return render_template("campaign_form.html", form=form, campaign=None)

        campaign = Campaign(
            slug=slug,
            internal_name=form.internal_name.data.strip(),
            hero_eyebrow=(form.hero_eyebrow.data or "").strip() or None,
            hero_title=form.hero_title.data.strip(),
            hero_highlight=(form.hero_highlight.data or "").strip() or None,
            hero_subtitle=(form.hero_subtitle.data or "").strip() or None,
            hero_cta_text=(form.hero_cta_text.data or "").strip() or None,
            hero_image_url=(form.hero_image_url.data or "").strip() or None,
            theme_color=(form.theme_color.data or "").strip() or None,
            status="rascunho",
            created_by_id=current_user.id,
        )
        db.session.add(campaign)
        db.session.commit()
        flash("Criativo salvo como rascunho.", "success")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    return render_template("campaign_form.html", form=form, campaign=None)


@campaigns_bp.route("/<int:campaign_id>")
@login_required
def detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    review_form = CampaignReviewForm()
    return render_template("campaign_detail.html", campaign=campaign, review_form=review_form)


@campaigns_bp.route("/<int:campaign_id>/editar", methods=["GET", "POST"])
@login_required
def edit_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    form = CampaignForm(obj=campaign)
    if form.validate_on_submit():
        slug = form.slug.data.strip().lower()
        existing = Campaign.query.filter(Campaign.slug == slug, Campaign.id != campaign.id).first()
        if existing:
            flash("Já existe outro criativo com esse slug.", "danger")
            return render_template("campaign_form.html", form=form, campaign=campaign)

        campaign.slug = slug
        campaign.internal_name = form.internal_name.data.strip()
        campaign.hero_eyebrow = (form.hero_eyebrow.data or "").strip() or None
        campaign.hero_title = form.hero_title.data.strip()
        campaign.hero_highlight = (form.hero_highlight.data or "").strip() or None
        campaign.hero_subtitle = (form.hero_subtitle.data or "").strip() or None
        campaign.hero_cta_text = (form.hero_cta_text.data or "").strip() or None
        campaign.hero_image_url = (form.hero_image_url.data or "").strip() or None
        campaign.theme_color = (form.theme_color.data or "").strip() or None

        # Editar um criativo publicado, em revisão ou arquivado volta pro
        # rascunho — qualquer mudança precisa passar por aprovação de novo.
        if campaign.status != "rascunho":
            campaign.status = "rascunho"
            campaign.reviewed_by_id = None
            campaign.review_note = None
            campaign.submitted_at = None
            campaign.published_at = None

        db.session.commit()
        flash("Criativo atualizado.", "success")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    return render_template("campaign_form.html", form=form, campaign=campaign)


@campaigns_bp.route("/<int:campaign_id>/preview")
@login_required
def preview(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    return render_template("landing.html", campaign=campaign, preview=True)


@campaigns_bp.route("/<int:campaign_id>/enviar-revisao", methods=["POST"])
@login_required
def submit_for_review(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.status != "rascunho":
        flash("Só é possível enviar para revisão um criativo em rascunho.", "warning")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    campaign.status = "em_revisao"
    campaign.submitted_at = datetime.utcnow()
    db.session.commit()
    flash("Criativo enviado para revisão.", "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign.id))


@campaigns_bp.route("/<int:campaign_id>/aprovar", methods=["POST"])
@login_required
@owner_required
def approve(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.status != "em_revisao":
        flash("Só é possível aprovar um criativo em revisão.", "warning")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    campaign.status = "publicado"
    campaign.reviewed_by_id = current_user.id
    campaign.published_at = datetime.utcnow()
    campaign.review_note = None
    db.session.commit()
    flash("Criativo aprovado e publicado em /lp/" + campaign.slug, "success")
    return redirect(url_for("campaigns.detail", campaign_id=campaign.id))


@campaigns_bp.route("/<int:campaign_id>/recusar", methods=["POST"])
@login_required
@owner_required
def reject(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.status != "em_revisao":
        flash("Só é possível recusar um criativo em revisão.", "warning")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    campaign.status = "rascunho"
    campaign.reviewed_by_id = current_user.id
    campaign.review_note = request.form.get("review_note", "").strip()[:2000] or None
    db.session.commit()
    flash("Criativo devolvido para ajustes.", "info")
    return redirect(url_for("campaigns.detail", campaign_id=campaign.id))


@campaigns_bp.route("/<int:campaign_id>/despublicar", methods=["POST"])
@login_required
@owner_required
def unpublish(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.status != "publicado":
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    campaign.status = "arquivado"
    db.session.commit()
    flash("Criativo despublicado.", "info")
    return redirect(url_for("campaigns.detail", campaign_id=campaign.id))


@campaigns_bp.route("/<int:campaign_id>/excluir", methods=["POST"])
@login_required
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.status not in ("rascunho", "arquivado"):
        flash("Só é possível excluir criativos em rascunho ou arquivados.", "warning")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))
    db.session.delete(campaign)
    db.session.commit()
    flash("Criativo excluído.", "success")
    return redirect(url_for("campaigns.list_campaigns"))
