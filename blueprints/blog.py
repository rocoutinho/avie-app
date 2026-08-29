from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints.auth import require_staff
from extensions import db
from forms import BlogPostForm, BlogPostReviewForm
from models import BlogPost

blog_bp = Blueprint("blog", __name__, url_prefix="/painel/blog")
blog_bp.before_request(require_staff)


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user.role != "owner":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@blog_bp.route("/")
@login_required
def list_posts():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template("blog_admin_list.html", posts=posts)


@blog_bp.route("/novo", methods=["GET", "POST"])
@login_required
def new_post():
    form = BlogPostForm()
    if form.validate_on_submit():
        slug = form.slug.data.strip().lower()
        if BlogPost.query.filter_by(slug=slug).first():
            flash("Já existe um artigo com esse slug.", "danger")
            return render_template("blog_admin_form.html", form=form, post=None)

        post = BlogPost(
            slug=slug,
            title=form.title.data.strip(),
            excerpt=form.excerpt.data.strip(),
            cover_image_url=(form.cover_image_url.data or "").strip() or None,
            author_name=form.author_name.data.strip(),
            body_markdown=form.body_markdown.data,
            status="rascunho",
            created_by_id=current_user.id,
        )
        db.session.add(post)
        db.session.commit()
        flash("Artigo salvo como rascunho.", "success")
        return redirect(url_for("blog.detail", post_id=post.id))
    return render_template("blog_admin_form.html", form=form, post=None)


@blog_bp.route("/<int:post_id>")
@login_required
def detail(post_id):
    post = BlogPost.query.get_or_404(post_id)
    review_form = BlogPostReviewForm()
    return render_template("blog_admin_detail.html", post=post, review_form=review_form)


@blog_bp.route("/<int:post_id>/editar", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    form = BlogPostForm(obj=post)
    if form.validate_on_submit():
        slug = form.slug.data.strip().lower()
        existing = BlogPost.query.filter(BlogPost.slug == slug, BlogPost.id != post.id).first()
        if existing:
            flash("Já existe outro artigo com esse slug.", "danger")
            return render_template("blog_admin_form.html", form=form, post=post)

        post.slug = slug
        post.title = form.title.data.strip()
        post.excerpt = form.excerpt.data.strip()
        post.cover_image_url = (form.cover_image_url.data or "").strip() or None
        post.author_name = form.author_name.data.strip()
        post.body_markdown = form.body_markdown.data

        # Editar um artigo publicado, em revisão ou arquivado volta pro
        # rascunho — qualquer mudança precisa passar por aprovação de novo.
        if post.status != "rascunho":
            post.status = "rascunho"
            post.reviewed_by_id = None
            post.review_note = None
            post.submitted_at = None
            post.published_at = None

        db.session.commit()
        flash("Artigo atualizado.", "success")
        return redirect(url_for("blog.detail", post_id=post.id))
    return render_template("blog_admin_form.html", form=form, post=post)


@blog_bp.route("/<int:post_id>/preview")
@login_required
def preview(post_id):
    post = BlogPost.query.get_or_404(post_id)
    return render_template("blog_post.html", post=post, preview=True)


@blog_bp.route("/<int:post_id>/enviar-revisao", methods=["POST"])
@login_required
def submit_for_review(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if post.status != "rascunho":
        flash("Só é possível enviar para revisão um artigo em rascunho.", "warning")
        return redirect(url_for("blog.detail", post_id=post.id))
    post.status = "em_revisao"
    post.submitted_at = datetime.utcnow()
    db.session.commit()
    flash("Artigo enviado para revisão.", "success")
    return redirect(url_for("blog.detail", post_id=post.id))


@blog_bp.route("/<int:post_id>/aprovar", methods=["POST"])
@login_required
@owner_required
def approve(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if post.status != "em_revisao":
        flash("Só é possível aprovar um artigo em revisão.", "warning")
        return redirect(url_for("blog.detail", post_id=post.id))
    post.status = "publicado"
    post.reviewed_by_id = current_user.id
    post.published_at = datetime.utcnow()
    post.review_note = None
    db.session.commit()
    flash("Artigo aprovado e publicado em /blog/" + post.slug, "success")
    return redirect(url_for("blog.detail", post_id=post.id))


@blog_bp.route("/<int:post_id>/recusar", methods=["POST"])
@login_required
@owner_required
def reject(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if post.status != "em_revisao":
        flash("Só é possível recusar um artigo em revisão.", "warning")
        return redirect(url_for("blog.detail", post_id=post.id))
    post.status = "rascunho"
    post.reviewed_by_id = current_user.id
    post.review_note = request.form.get("review_note", "").strip()[:2000] or None
    db.session.commit()
    flash("Artigo devolvido para ajustes.", "info")
    return redirect(url_for("blog.detail", post_id=post.id))


@blog_bp.route("/<int:post_id>/despublicar", methods=["POST"])
@login_required
@owner_required
def unpublish(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if post.status != "publicado":
        return redirect(url_for("blog.detail", post_id=post.id))
    post.status = "arquivado"
    db.session.commit()
    flash("Artigo despublicado.", "info")
    return redirect(url_for("blog.detail", post_id=post.id))


@blog_bp.route("/<int:post_id>/excluir", methods=["POST"])
@login_required
def delete_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    if post.status not in ("rascunho", "arquivado"):
        flash("Só é possível excluir artigos em rascunho ou arquivados.", "warning")
        return redirect(url_for("blog.detail", post_id=post.id))
    db.session.delete(post)
    db.session.commit()
    flash("Artigo excluído.", "success")
    return redirect(url_for("blog.list_posts"))
